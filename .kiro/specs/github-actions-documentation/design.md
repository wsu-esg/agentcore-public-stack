# Design Document: GitHub Actions Configuration Documentation

## Overview

This design specifies a documentation generation system that creates comprehensive reference documentation for GitHub Actions configuration in the AgentCore Public Stack project. The system will analyze 5 workflow files, extract all GitHub Variables and Secrets, trace their usage through scripts and CDK stacks, determine requirement status, identify default values, and generate a well-structured markdown document at `.github/README-ACTIONS.md`.

The documentation will serve as the single source of truth for developers setting up GitHub Actions for CI/CD deployment, eliminating confusion about which configuration values are needed and where they come from.

## Architecture

### High-Level Flow

```
Workflow Files (.github/workflows/*.yml)
         ↓
   [Extraction Layer]
         ↓
Configuration Scripts (scripts/common/load-env.sh)
         ↓
   [Tracing Layer]
         ↓
CDK Configuration (infrastructure/lib/config.ts, cdk.context.json)
         ↓
   [Analysis Layer]
         ↓
Documentation Generator
         ↓
README-ACTIONS.md
```

### Component Architecture

The system consists of four main components:

1. **Workflow Parser**: Extracts variables and secrets from YAML workflow files
2. **Configuration Tracer**: Traces configuration values through scripts and CDK
3. **Requirement Analyzer**: Determines if values are required or optional
4. **Documentation Generator**: Produces formatted markdown output

## Components and Interfaces

### 1. Workflow Parser

**Purpose**: Extract all GitHub Variables (`vars.*`) and Secrets (`secrets.*`) from workflow YAML files.

**Input**:
- Workflow file path (string)
- Workflow YAML content (string)

**Output**:
```typescript
interface WorkflowConfig {
  workflowName: string;
  variables: ConfigValue[];
  secrets: ConfigValue[];
}

interface ConfigValue {
  name: string;              // e.g., "AWS_REGION", "CDK_AWS_ACCOUNT"
  type: 'variable' | 'secret';
  usageLocations: string[];  // Job names or step names where used
}
```

**Algorithm**:
1. Parse YAML using a YAML parser library
2. Traverse all `env:` blocks at workflow, job, and step levels
3. Extract references matching patterns:
   - `${{ vars.VARIABLE_NAME }}`
   - `${{ secrets.SECRET_NAME }}`
4. Record the location (job/step) where each is used
5. Deduplicate by name while preserving all usage locations

**Edge Cases**:
- Variables used in conditional expressions (`if:` statements)
- Variables used in matrix strategies
- Variables used in reusable workflow calls

### 2. Configuration Tracer

**Purpose**: Trace configuration values from workflows through scripts to CDK stacks to understand their flow and find default values.

**Input**:
- ConfigValue from Workflow Parser
- File paths to check: `scripts/common/load-env.sh`, `infrastructure/lib/config.ts`, `infrastructure/cdk.context.json`

**Output**:
```typescript
interface TracedConfig extends ConfigValue {
  defaultValue?: string | number | boolean;
  defaultSource?: 'workflow' | 'load-env.sh' | 'config.ts' | 'cdk.context.json';
  cdkUsage?: {
    configKey: string;        // Key in config.ts interface
    stacksUsing: string[];    // Which stacks use this config
  };
}
```

**Tracing Logic**:

For each configuration value:

1. **Check workflow YAML** for inline defaults:
   ```yaml
   env:
     CDK_REQUIRE_APPROVAL: never  # This is a default
   ```

2. **Check `load-env.sh`** for export statements with defaults:
   ```bash
   export CDK_AWS_REGION="${CDK_AWS_REGION:-$(get_json_value "awsRegion" "${CONTEXT_FILE}")}"
   # Default comes from cdk.context.json if env var not set
   ```

3. **Check `config.ts`** for fallback values:
   ```typescript
   production: parseBooleanEnv(process.env.CDK_PRODUCTION, true), // Default: true
   ```

4. **Check `cdk.context.json`** for context defaults:
   ```json
   {
     "awsRegion": "us-west-2",
     "appApi": {
       "cpu": 512
     }
   }
   ```

**Parsing Strategies**:
- **YAML**: Use YAML parser library
- **Shell script**: Regex patterns for `export VAR="${VAR:-default}"` and `get_json_value` calls
- **TypeScript**: AST parsing or regex for assignment patterns with `||` or default parameters
- **JSON**: Standard JSON parser

### 3. Requirement Analyzer

**Purpose**: Determine if a configuration value is Required or Optional based on whether it has defaults and whether downstream resources require it.

**Input**:
- TracedConfig from Configuration Tracer

**Output**:
```typescript
interface AnalyzedConfig extends TracedConfig {
  required: boolean;
  requirementReason: string;  // Human-readable explanation
}
```

**Decision Logic**:

A configuration value is **Required** if:
1. It has NO default value in any location (workflow, load-env.sh, config.ts, cdk.context.json), AND
2. The downstream CDK resource or script requires it to function

A configuration value is **Optional** if:
1. It has a default value in any location, OR
2. The downstream resource can function without it (e.g., optional features)

**Determining Downstream Requirements**:

For CDK configuration:
- Check if the config property is marked with `?` (optional) in TypeScript interface
- Check if the config is used in conditional logic (`if (config.value)`)
- Check if validation in `config.ts` throws errors for missing values

For AWS resources:
- Use AWS MCP tools to check resource documentation
- Example: `CDK_AWS_ACCOUNT` is required because AWS CDK cannot deploy without an account ID
- Example: `CDK_CERTIFICATE_ARN` is optional because ALB can work without HTTPS

**Examples**:

```typescript
// Required: No default, validation throws error
if (!projectPrefix) {
  throw new Error('CDK_PROJECT_PREFIX is required');
}

// Optional: Has default value
production: parseBooleanEnv(process.env.CDK_PRODUCTION, true), // Default: true

// Optional: Marked optional in interface
certificateArn?: string;

// Optional: Used conditionally
if (config.certificateArn) {
  // Configure HTTPS
}
```

### 4. Documentation Generator

**Purpose**: Generate formatted markdown documentation from analyzed configuration values.

**Input**:
- Map of workflow name to AnalyzedConfig[]
- Template for documentation structure

**Output**:
- Markdown string to be written to `.github/README-ACTIONS.md`

**Document Structure**:

```markdown
# GitHub Actions Configuration

## GitHub Variables and Secrets

This document lists all GitHub Variables and Secrets required for CI/CD workflows.

### Infrastructure Stack

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| AWS_REGION | Variable | Yes | `us-west-2` | AWS region for deployment |
| CDK_AWS_ACCOUNT | Secret | Yes | None | 12-digit AWS account ID |
| ... | ... | ... | ... | ... |

### App API Stack

[Same table structure]

### Inference API Stack

[Same table structure]

### Frontend Stack

[Same table structure]

### Gateway Stack

[Same table structure]
```

**Formatting Rules**:
- Use markdown tables for consistency and scannability
- Sort entries alphabetically by name within each stack
- Use backticks for default values: `` `true` ``, `` `us-west-2` ``
- Use "None" for missing defaults
- Keep descriptions to one sentence (max 100 characters)
- Use consistent capitalization: "Yes"/"No" for Required column

**Description Generation**:

Descriptions should be derived from:
1. Comments in workflow files
2. Variable names (e.g., `CDK_VPC_CIDR` → "CIDR block for VPC")
3. Usage context in CDK stacks
4. AWS resource documentation (via MCP tools)

**Description Templates**:
- `AWS_REGION`: "AWS region for resource deployment"
- `CDK_PROJECT_PREFIX`: "Prefix for all resource names"
- `CDK_*_CPU`: "CPU units for [service] ECS task"
- `CDK_*_MEMORY`: "Memory (MB) for [service] ECS task"
- `CDK_*_ENABLED`: "Enable/disable [feature]"
- `*_API_KEY`: "API key for [service] integration"

## Data Models

### Configuration Value Lifecycle

```
WorkflowConfig (raw extraction)
    ↓
TracedConfig (with defaults and CDK usage)
    ↓
AnalyzedConfig (with requirement status)
    ↓
DocumentationEntry (formatted for output)
```

### Complete Data Model

```typescript
interface DocumentationEntry {
  name: string;
  type: 'Variable' | 'Secret';
  required: 'Yes' | 'No';
  default: string;  // Formatted for display, "None" if missing
  description: string;
}

interface StackDocumentation {
  stackName: string;
  entries: DocumentationEntry[];
}

interface CompleteDocumentation {
  stacks: StackDocumentation[];
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: File Creation
*For any* execution of the documentation generator, the output file `.github/README-ACTIONS.md` should exist after completion.
**Validates: Requirements 1.1**

### Property 2: Complete Variable Extraction
*For any* workflow file containing variables referenced via `vars.*` syntax, all such variables should be extracted and included in the documentation.
**Validates: Requirements 2.1**

### Property 3: Complete Secret Extraction
*For any* workflow file containing secrets referenced via `secrets.*` syntax, all such secrets should be extracted and included in the documentation.
**Validates: Requirements 2.2**

### Property 4: Name Preservation
*For any* configuration value extracted from a workflow, the name in the documentation should exactly match the name in the workflow file.
**Validates: Requirements 2.3**

### Property 5: Type Classification
*For any* configuration value, if it uses `vars.*` syntax it should be classified as "Variable", and if it uses `secrets.*` syntax it should be classified as "Secret".
**Validates: Requirements 2.4**

### Property 6: Requirement Classification Consistency
*For any* configuration value with a default value in any location (workflow, load-env.sh, config.ts, cdk.context.json), it should be marked as "Optional" in the documentation.
**Validates: Requirements 3.3**

### Property 7: Default Value Detection
*For any* configuration value with a default specified in workflow YAML, load-env.sh, config.ts, or cdk.context.json, that default value should be documented.
**Validates: Requirements 4.2, 4.3, 4.4, 4.5**

### Property 8: Format Consistency
*For any* two stack subsections in the generated documentation, they should use the same format structure (both tables or both lists with identical field ordering).
**Validates: Requirements 6.2**

### Property 9: Description Presence
*For any* configuration value in the documentation, there should be a non-empty description field.
**Validates: Requirements 5.1**

### Property 10: Description Conciseness
*For any* description in the documentation, it should be 150 characters or less.
**Validates: Requirements 5.3**

### Property 11: Scope Exclusion
*For any* generated documentation, it should not contain workflow job names, step names, or deployment procedure instructions.
**Validates: Requirements 12.1, 12.2, 12.3, 12.4**

## Error Handling

### Workflow Parsing Errors

**Error**: Invalid YAML syntax in workflow file
**Handling**: Log error with file name and line number, skip that workflow, continue with others

**Error**: Workflow file not found
**Handling**: Log warning, skip that workflow, continue with others

**Error**: Unexpected workflow structure (missing expected keys)
**Handling**: Log warning, extract what's possible, continue

### Configuration Tracing Errors

**Error**: Cannot parse load-env.sh (syntax error)
**Handling**: Log error, continue without shell script defaults, rely on other sources

**Error**: Cannot parse config.ts (TypeScript syntax error)
**Handling**: Log error, continue without TypeScript defaults, rely on other sources

**Error**: Cannot parse cdk.context.json (invalid JSON)
**Handling**: Log error, continue without JSON defaults, rely on other sources

**Error**: Configuration value not found in any default source
**Handling**: Mark as "None" for default value, continue

### Requirement Analysis Errors

**Error**: Cannot determine if value is required (ambiguous usage)
**Handling**: Default to marking as "Required" (safer choice), log warning for manual review

**Error**: AWS MCP tool unavailable or returns error
**Handling**: Fall back to heuristic analysis (check for `?` in TypeScript, conditional usage), log warning

### Documentation Generation Errors

**Error**: Cannot write to output file (permissions)
**Handling**: Throw error with clear message about file permissions

**Error**: No configuration values found for a stack
**Handling**: Include stack section with message "No configuration required" or "Configuration inherited from Infrastructure Stack"

## Testing Strategy

### Unit Tests

**Workflow Parser Tests**:
- Test extraction of variables from `env:` blocks at different levels (workflow, job, step)
- Test extraction of secrets from `env:` blocks
- Test handling of variables in conditional expressions
- Test deduplication of repeated variable references
- Test parsing of all 5 actual workflow files

**Configuration Tracer Tests**:
- Test extraction of defaults from load-env.sh export statements
- Test extraction of defaults from config.ts assignments
- Test extraction of defaults from cdk.context.json
- Test handling of missing default sources
- Test tracing of specific known variables (e.g., `CDK_AWS_REGION`)

**Requirement Analyzer Tests**:
- Test classification of values with defaults as Optional
- Test classification of values without defaults as Required
- Test handling of optional TypeScript properties (`?`)
- Test handling of conditional usage patterns
- Test specific known required values (e.g., `CDK_AWS_ACCOUNT`)

**Documentation Generator Tests**:
- Test markdown table generation
- Test sorting of entries alphabetically
- Test formatting of default values
- Test generation of all 5 stack sections
- Test handling of empty configuration sets

### Property-Based Tests

Each property test should run a minimum of 100 iterations and be tagged with the format:
**Feature: github-actions-documentation, Property {number}: {property_text}**

**Property 1 Test**: Generate documentation, verify file exists at expected path
**Property 2 Test**: Create workflow with random variables, verify all extracted
**Property 3 Test**: Create workflow with random secrets, verify all extracted
**Property 4 Test**: Create workflow with specific names, verify exact match in output
**Property 5 Test**: Create workflow with mix of vars/secrets, verify correct classification
**Property 6 Test**: Create config with random defaults, verify all marked Optional
**Property 7 Test**: Create config with defaults in random locations, verify all documented
**Property 8 Test**: Generate documentation, verify all sections use same format
**Property 9 Test**: Generate documentation, verify all entries have descriptions
**Property 10 Test**: Generate documentation, verify all descriptions under 150 chars
**Property 11 Test**: Generate documentation, verify no workflow/deployment details present

### Integration Tests

**End-to-End Test**:
1. Run documentation generator on actual project workflows
2. Verify output file exists and is valid markdown
3. Verify all 5 stacks are documented
4. Verify known required variables are marked Required
5. Verify known optional variables are marked Optional
6. Verify known defaults are documented correctly
7. Manually review a sample of descriptions for accuracy

**Regression Test**:
1. Keep a snapshot of generated documentation
2. After code changes, regenerate and compare
3. Flag any unexpected changes for review

## Implementation Notes

### Technology Choices

**Language**: TypeScript (matches infrastructure code, good YAML/JSON support)

**Libraries**:
- `js-yaml`: YAML parsing for workflow files
- `@typescript-eslint/parser`: TypeScript AST parsing for config.ts
- `glob`: File pattern matching for finding workflows

**Execution**:
- Can be run as a standalone script: `npm run generate-docs`
- Can be integrated into CI to verify documentation is up-to-date
- Can be run manually by developers when adding new configuration

### File Locations

**Input Files**:
- `.github/workflows/infrastructure.yml`
- `.github/workflows/app-api.yml`
- `.github/workflows/inference-api.yml`
- `.github/workflows/frontend.yml`
- `.github/workflows/gateway.yml`
- `scripts/common/load-env.sh`
- `infrastructure/lib/config.ts`
- `infrastructure/cdk.context.json`

**Output File**:
- `.github/README-ACTIONS.md`

### Maintenance

**When to Update**:
- When adding new GitHub Variables or Secrets to workflows
- When changing default values in config files
- When adding new workflows
- When changing requirement status of existing configuration

**Verification**:
- Run `npm run generate-docs` after configuration changes
- Review diff to ensure changes are expected
- Commit updated documentation with configuration changes

### Future Enhancements

**Potential Additions** (out of scope for initial implementation):
- Generate environment-specific documentation (dev vs prod)
- Include example values for each configuration
- Add links to AWS documentation for AWS-specific config
- Generate JSON schema for validation
- Create interactive web version of documentation
- Add configuration validation script that checks GitHub settings against documentation
