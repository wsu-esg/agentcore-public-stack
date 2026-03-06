import * as cdk from 'aws-cdk-lib';
import * as agentcore from 'aws-cdk-lib/aws-bedrockagentcore';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';
import { AppConfig, getResourceName, applyStandardTags } from './config';

export interface GatewayStackProps extends cdk.StackProps {
  config: AppConfig;
}

/**
 * Gateway Stack - AWS Bedrock AgentCore Gateway
 *
 * This stack creates:
 * - AgentCore Gateway with MCP protocol and AWS_IAM authorization
 * - IAM roles with appropriate permissions
 *
 * Gateway Targets (search tools, etc.) are managed externally.
 */
export class GatewayStack extends cdk.Stack {
  public readonly gateway: agentcore.CfnGateway;

  constructor(scope: Construct, id: string, props: GatewayStackProps) {
    super(scope, id, props);

    const { config } = props;

    // Apply standard tags
    applyStandardTags(this, config);

    // ============================================================
    // Gateway Execution Role
    // ============================================================

    const gatewayRole = new iam.Role(this, 'GatewayExecutionRole', {
      roleName: getResourceName(config, 'gateway-role'),
      assumedBy: new iam.ServicePrincipal('bedrock-agentcore.amazonaws.com'),
      description: 'Execution role for AgentCore Gateway',
    });

    // Lambda invocation permissions
    gatewayRole.addToPolicy(
      new iam.PolicyStatement({
        sid: 'LambdaInvokeAccess',
        effect: iam.Effect.ALLOW,
        actions: ['lambda:InvokeFunction'],
        resources: [
          `arn:aws:lambda:${this.region}:${this.account}:function:${config.projectPrefix}-mcp-*`,
        ],
      })
    );

    // CloudWatch Logs for Gateway
    gatewayRole.addToPolicy(
      new iam.PolicyStatement({
        sid: 'GatewayLogsAccess',
        effect: iam.Effect.ALLOW,
        actions: ['logs:CreateLogGroup', 'logs:CreateLogStream', 'logs:PutLogEvents'],
        resources: [
          `arn:aws:logs:${this.region}:${this.account}:log-group:/aws/bedrock-agentcore/gateways/*`,
        ],
      })
    );

    // ============================================================
    // AgentCore Gateway
    // ============================================================

    this.gateway = new agentcore.CfnGateway(this, 'MCPGateway', {
      name: getResourceName(config, 'mcp-gateway'),
      description: 'MCP Gateway for external tools',
      roleArn: gatewayRole.roleArn,

      // Authentication: AWS_IAM (SigV4)
      authorizerType: 'AWS_IAM',

      // Protocol: MCP
      protocolType: 'MCP',

      // Exception level: Only DEBUG is supported
      exceptionLevel: 'DEBUG',

      // MCP Protocol Configuration
      protocolConfiguration: {
        mcp: {
          supportedVersions: ['2025-11-25'],
          searchType: 'SEMANTIC',
        },
      },
    });

    const gatewayArn = `arn:aws:bedrock-agentcore:${this.region}:${this.account}:gateway/${this.gateway.attrGatewayIdentifier}`;
    const gatewayUrl = this.gateway.attrGatewayUrl;
    const gatewayId = this.gateway.attrGatewayIdentifier;

    // ============================================================
    // SSM Parameters
    // ============================================================

    new ssm.StringParameter(this, 'GatewayUrlParameter', {
      parameterName: `/${config.projectPrefix}/gateway/url`,
      stringValue: gatewayUrl,
      description: 'AgentCore Gateway URL for remote invocation (SigV4 authenticated)',
      tier: ssm.ParameterTier.STANDARD,
    });

    new ssm.StringParameter(this, 'GatewayIdParameter', {
      parameterName: `/${config.projectPrefix}/gateway/id`,
      stringValue: gatewayId,
      description: 'AgentCore Gateway Identifier',
      tier: ssm.ParameterTier.STANDARD,
    });

    // ============================================================
    // Outputs
    // ============================================================

    new cdk.CfnOutput(this, 'GatewayArn', {
      value: gatewayArn,
      description: 'AgentCore Gateway ARN',
      exportName: getResourceName(config, 'gateway-arn'),
    });

    new cdk.CfnOutput(this, 'GatewayUrl', {
      value: gatewayUrl,
      description: 'AgentCore Gateway URL (requires SigV4 authentication)',
      exportName: getResourceName(config, 'gateway-url'),
    });

    new cdk.CfnOutput(this, 'GatewayId', {
      value: gatewayId,
      description: 'AgentCore Gateway Identifier',
      exportName: getResourceName(config, 'gateway-id'),
    });

    new cdk.CfnOutput(this, 'GatewayStatus', {
      value: this.gateway.attrStatus,
      description: 'Gateway Status',
    });

    new cdk.CfnOutput(this, 'UsageInstructions', {
      value: `
Gateway URL: ${gatewayUrl}
Authentication: AWS_IAM (SigV4)

To test Gateway connectivity:
  aws bedrock-agentcore invoke-gateway \\
    --gateway-identifier ${gatewayId} \\
    --region ${this.region}
      `.trim(),
      description: 'Usage instructions for Gateway',
    });
  }
}
