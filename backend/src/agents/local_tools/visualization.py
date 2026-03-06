"""
Simple Visualization Tool - Strands Native
Creates chart specifications for frontend rendering using Chart.js format
"""

import json
import logging
from typing import Any, Literal
from strands import tool

logger = logging.getLogger(__name__)

# Default color palette using rgba for Chart.js compatibility
DEFAULT_COLORS = [
    "rgba(59, 130, 246, 0.8)",   # Blue
    "rgba(16, 185, 129, 0.8)",   # Green
    "rgba(245, 158, 11, 0.8)",   # Amber
    "rgba(239, 68, 68, 0.8)",    # Red
    "rgba(139, 92, 246, 0.8)",   # Purple
    "rgba(236, 72, 153, 0.8)",   # Pink
    "rgba(20, 184, 166, 0.8)",   # Teal
    "rgba(249, 115, 22, 0.8)",   # Orange
]


def validate_chart_data(chart_type: str, data: list[dict[str, Any]]) -> tuple[bool, str | None]:
    """Validate chart data structure"""
    if not data:
        return False, "Data array is empty"

    if chart_type in ["pie", "doughnut", "polarArea"]:
        # Pie/doughnut/polar area charts need segment/value pairs
        for item in data:
            if "segment" not in item or "value" not in item:
                # Try to find alternative field names
                if not any(k in item for k in ["name", "label", "category"]):
                    return False, f"{chart_type.title()} chart data must have 'segment' (or 'name'/'label') field"
                if not any(k in item for k in ["value", "count", "amount"]):
                    return False, f"{chart_type.title()} chart data must have 'value' (or 'count'/'amount') field"

    elif chart_type in ["bar", "line", "area"]:
        # Bar/line/area charts need x/y pairs
        for item in data:
            if "x" not in item or "y" not in item:
                return False, f"{chart_type.title()} chart data must have 'x' and 'y' fields"

    elif chart_type in ["scatter", "bubble"]:
        # Scatter/bubble charts need x/y pairs (bubble also needs r for radius)
        for item in data:
            if "x" not in item or "y" not in item:
                return False, f"{chart_type.title()} chart data must have 'x' and 'y' fields"
            if chart_type == "bubble" and "r" not in item:
                return False, "Bubble chart data must have 'r' (radius) field"

    elif chart_type == "radar":
        # Radar charts need label/value pairs
        for item in data:
            if "label" not in item or "value" not in item:
                if not any(k in item for k in ["name", "category", "axis"]):
                    return False, "Radar chart data must have 'label' (or 'name'/'category') field"
                if not any(k in item for k in ["value", "score", "amount"]):
                    return False, "Radar chart data must have 'value' (or 'score'/'amount') field"

    return True, None


def normalize_chart_data(chart_type: str, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize chart data to standard format"""
    normalized = []

    for item in data:
        normalized_item = dict(item)

        if chart_type in ["pie", "doughnut", "polarArea"]:
            # Normalize segment field
            if "segment" not in normalized_item:
                for alt_name in ["name", "label", "category", "key"]:
                    if alt_name in normalized_item:
                        normalized_item["segment"] = normalized_item[alt_name]
                        break

            # Normalize value field
            if "value" not in normalized_item:
                for alt_name in ["count", "amount", "total", "size"]:
                    if alt_name in normalized_item:
                        normalized_item["value"] = normalized_item[alt_name]
                        break

        elif chart_type == "radar":
            # Normalize label field
            if "label" not in normalized_item:
                for alt_name in ["name", "category", "axis"]:
                    if alt_name in normalized_item:
                        normalized_item["label"] = normalized_item[alt_name]
                        break

            # Normalize value field
            if "value" not in normalized_item:
                for alt_name in ["score", "amount", "count"]:
                    if alt_name in normalized_item:
                        normalized_item["value"] = normalized_item[alt_name]
                        break

        normalized.append(normalized_item)

    return normalized


def _to_chartjs_bar_line(data: list[dict[str, Any]], chart_type: str, title: str, x_label: str, y_label: str) -> dict:
    """Convert bar/line data to Chart.js format"""
    labels = [item["x"] for item in data]
    values = [item["y"] for item in data]
    colors = [item.get("color", DEFAULT_COLORS[i % len(DEFAULT_COLORS)]) for i, item in enumerate(data)]

    return {
        "chartType": chart_type,
        "title": title,
        "data": {
            "labels": labels,
            "datasets": [{
                "label": title or "Value",
                "data": values,
                "backgroundColor": colors,
                "borderColor": colors,
                "borderWidth": 1,
                "borderRadius": 4 if chart_type == "bar" else 0,
                "tension": 0.3 if chart_type == "line" else 0,
            }]
        },
        "options": {
            "responsive": True,
            "maintainAspectRatio": False,
            "plugins": {
                "legend": {"display": bool(title)},
                "title": {"display": bool(title), "text": title}
            },
            "scales": {
                "x": {
                    "title": {"display": bool(x_label), "text": x_label},
                    "grid": {"display": False}
                },
                "y": {
                    "title": {"display": bool(y_label), "text": y_label},
                    "beginAtZero": True
                }
            }
        }
    }


def _to_chartjs_pie(data: list[dict[str, Any]], chart_type: str, title: str) -> dict:
    """Convert pie/doughnut/polarArea data to Chart.js format"""
    labels = [item["segment"] for item in data]
    values = [item["value"] for item in data]
    colors = [item.get("color", DEFAULT_COLORS[i % len(DEFAULT_COLORS)]) for i, item in enumerate(data)]

    options: dict[str, Any] = {
        "responsive": True,
        "maintainAspectRatio": False,
        "plugins": {
            "legend": {"display": True, "position": "right"},
            "title": {"display": bool(title), "text": title}
        }
    }

    # Add cutout for doughnut charts
    if chart_type == "doughnut":
        options["cutout"] = "50%"

    return {
        "chartType": chart_type,
        "title": title,
        "data": {
            "labels": labels,
            "datasets": [{
                "data": values,
                "backgroundColor": colors,
                "borderColor": "#ffffff",
                "borderWidth": 2,
                "hoverOffset": 4
            }]
        },
        "options": options
    }


def _to_chartjs_area(data: list[dict[str, Any]], title: str, x_label: str, y_label: str) -> dict:
    """Convert area chart data to Chart.js format (line chart with fill)"""
    labels = [item["x"] for item in data]
    values = [item["y"] for item in data]
    color = data[0].get("color", DEFAULT_COLORS[0]) if data else DEFAULT_COLORS[0]

    return {
        "chartType": "line",  # Area is a line chart with fill
        "title": title,
        "data": {
            "labels": labels,
            "datasets": [{
                "label": title or "Value",
                "data": values,
                "backgroundColor": color.replace("0.8)", "0.3)") if "rgba" in color else color,
                "borderColor": color,
                "borderWidth": 2,
                "fill": True,
                "tension": 0.4,
            }]
        },
        "options": {
            "responsive": True,
            "maintainAspectRatio": False,
            "plugins": {
                "legend": {"display": bool(title)},
                "title": {"display": bool(title), "text": title}
            },
            "scales": {
                "x": {
                    "title": {"display": bool(x_label), "text": x_label},
                    "grid": {"display": False}
                },
                "y": {
                    "title": {"display": bool(y_label), "text": y_label},
                    "beginAtZero": True
                }
            }
        }
    }


def _to_chartjs_scatter(data: list[dict[str, Any]], title: str, x_label: str, y_label: str) -> dict:
    """Convert scatter chart data to Chart.js format"""
    points = [{"x": item["x"], "y": item["y"]} for item in data]
    colors = [item.get("color", DEFAULT_COLORS[i % len(DEFAULT_COLORS)]) for i, item in enumerate(data)]

    return {
        "chartType": "scatter",
        "title": title,
        "data": {
            "datasets": [{
                "label": title or "Data Points",
                "data": points,
                "backgroundColor": colors,
                "borderColor": colors,
                "pointRadius": 6,
                "pointHoverRadius": 8,
            }]
        },
        "options": {
            "responsive": True,
            "maintainAspectRatio": False,
            "plugins": {
                "legend": {"display": bool(title)},
                "title": {"display": bool(title), "text": title}
            },
            "scales": {
                "x": {
                    "type": "linear",
                    "position": "bottom",
                    "title": {"display": bool(x_label), "text": x_label}
                },
                "y": {
                    "title": {"display": bool(y_label), "text": y_label},
                    "beginAtZero": True
                }
            }
        }
    }


def _to_chartjs_bubble(data: list[dict[str, Any]], title: str, x_label: str, y_label: str) -> dict:
    """Convert bubble chart data to Chart.js format"""
    points = [{"x": item["x"], "y": item["y"], "r": item["r"]} for item in data]
    colors = [item.get("color", DEFAULT_COLORS[i % len(DEFAULT_COLORS)]) for i, item in enumerate(data)]

    return {
        "chartType": "bubble",
        "title": title,
        "data": {
            "datasets": [{
                "label": title or "Data Points",
                "data": points,
                "backgroundColor": colors,
                "borderColor": [c.replace("0.8)", "1)") if "rgba" in c else c for c in colors],
                "borderWidth": 1,
            }]
        },
        "options": {
            "responsive": True,
            "maintainAspectRatio": False,
            "plugins": {
                "legend": {"display": bool(title)},
                "title": {"display": bool(title), "text": title}
            },
            "scales": {
                "x": {
                    "type": "linear",
                    "position": "bottom",
                    "title": {"display": bool(x_label), "text": x_label}
                },
                "y": {
                    "title": {"display": bool(y_label), "text": y_label},
                    "beginAtZero": True
                }
            }
        }
    }


def _to_chartjs_radar(data: list[dict[str, Any]], title: str) -> dict:
    """Convert radar chart data to Chart.js format"""
    labels = [item["label"] for item in data]
    values = [item["value"] for item in data]
    color = data[0].get("color", DEFAULT_COLORS[0]) if data else DEFAULT_COLORS[0]

    # Calculate sensible tick settings based on data range
    max_value = max(values) if values else 100
    # Round up to a nice number for the max
    if max_value <= 10:
        suggested_max = 10
    elif max_value <= 100:
        suggested_max = ((max_value // 10) + 1) * 10  # Round up to nearest 10
    else:
        suggested_max = ((max_value // 100) + 1) * 100  # Round up to nearest 100

    return {
        "chartType": "radar",
        "title": title,
        "data": {
            "labels": labels,
            "datasets": [{
                "label": title or "Values",
                "data": values,
                "backgroundColor": color.replace("0.8)", "0.2)") if "rgba" in color else color,
                "borderColor": color,
                "borderWidth": 2,
                "pointBackgroundColor": color,
                "pointBorderColor": "#ffffff",
                "pointHoverBackgroundColor": "#ffffff",
                "pointHoverBorderColor": color,
            }]
        },
        "options": {
            "responsive": True,
            "maintainAspectRatio": False,
            "plugins": {
                "legend": {"display": bool(title)},
                "title": {"display": bool(title), "text": title}
            },
            "scales": {
                "r": {
                    "beginAtZero": True,
                    "suggestedMax": suggested_max,
                    "ticks": {
                        "count": 5  # Show ~5 tick marks regardless of data range
                    }
                }
            }
        }
    }


# All supported chart types
SUPPORTED_CHART_TYPES = ["bar", "line", "pie", "doughnut", "area", "scatter", "bubble", "radar", "polarArea"]


@tool
def create_visualization(
    chart_type: Literal["bar", "line", "pie", "doughnut", "area", "scatter", "bubble", "radar", "polarArea"],
    data: list[dict[str, Any]],
    title: str = "",
    x_label: str = "",
    y_label: str = ""
) -> str:
    """
    Create interactive chart visualizations from data with custom colors.

    This tool generates Chart.js specifications that the frontend renders inline
    in the conversation. Supports multiple chart types for different data visualizations.

    Args:
        chart_type: Type of chart to create:
            - "bar": Vertical bar chart for comparing categories
            - "line": Line chart for trends over time
            - "area": Filled area chart (line chart with shading)
            - "pie": Pie chart for proportions
            - "doughnut": Doughnut chart (pie with center cutout)
            - "polarArea": Polar area chart (pie with equal angles, varying radius)
            - "scatter": Scatter plot for correlation between two variables
            - "bubble": Bubble chart (scatter with size dimension)
            - "radar": Radar/spider chart for multivariate data
        data: Array of data objects (format depends on chart type):
            - bar/line/area: [{"x": label, "y": value, "color": "rgba(...)"}]
            - pie/doughnut/polarArea: [{"segment": name, "value": number, "color": "rgba(...)"}]
            - scatter: [{"x": number, "y": number, "color": "rgba(...)"}]
            - bubble: [{"x": number, "y": number, "r": radius, "color": "rgba(...)"}]
            - radar: [{"label": axis_name, "value": number, "color": "rgba(...)"}]
            - Color field is always optional; defaults will be used if not provided
        title: Chart title (optional)
        x_label: X-axis label (for bar/line/area/scatter/bubble charts)
        y_label: Y-axis label (for bar/line/area/scatter/bubble charts)

    Returns:
        Chart specification rendered inline in conversation

    Examples:
        # Bar chart
        create_visualization(
            chart_type="bar",
            data=[{"x": "Q1", "y": 100}, {"x": "Q2", "y": 150}, {"x": "Q3", "y": 120}],
            title="Quarterly Sales"
        )

        # Line chart with trend
        create_visualization(
            chart_type="line",
            data=[{"x": "Mon", "y": 20}, {"x": "Tue", "y": 35}, {"x": "Wed", "y": 28}],
            title="Daily Active Users"
        )

        # Area chart
        create_visualization(
            chart_type="area",
            data=[{"x": "Jan", "y": 10}, {"x": "Feb", "y": 25}, {"x": "Mar", "y": 40}],
            title="Cumulative Growth"
        )

        # Pie chart
        create_visualization(
            chart_type="pie",
            data=[
                {"segment": "Desktop", "value": 60},
                {"segment": "Mobile", "value": 30},
                {"segment": "Tablet", "value": 10}
            ],
            title="Traffic by Device"
        )

        # Doughnut chart
        create_visualization(
            chart_type="doughnut",
            data=[{"segment": "Complete", "value": 75}, {"segment": "Remaining", "value": 25}],
            title="Project Progress"
        )

        # Polar Area chart
        create_visualization(
            chart_type="polarArea",
            data=[
                {"segment": "Research", "value": 11},
                {"segment": "Design", "value": 16},
                {"segment": "Development", "value": 7}
            ],
            title="Time Allocation"
        )

        # Scatter chart
        create_visualization(
            chart_type="scatter",
            data=[{"x": 10, "y": 20}, {"x": 15, "y": 10}, {"x": 20, "y": 30}],
            title="Height vs Weight",
            x_label="Height (cm)",
            y_label="Weight (kg)"
        )

        # Bubble chart (x, y position + r for bubble size)
        create_visualization(
            chart_type="bubble",
            data=[
                {"x": 20, "y": 30, "r": 15},
                {"x": 40, "y": 10, "r": 10},
                {"x": 30, "y": 25, "r": 20}
            ],
            title="Market Analysis",
            x_label="Market Share",
            y_label="Growth Rate"
        )

        # Radar chart
        create_visualization(
            chart_type="radar",
            data=[
                {"label": "Speed", "value": 65},
                {"label": "Reliability", "value": 59},
                {"label": "Comfort", "value": 90},
                {"label": "Safety", "value": 81},
                {"label": "Efficiency", "value": 56}
            ],
            title="Product Comparison"
        )
    """
    try:
        # Validate input
        if chart_type not in SUPPORTED_CHART_TYPES:
            error_dict = {
                "success": False,
                "error": f"Invalid chart type: {chart_type}. Must be one of: {', '.join(SUPPORTED_CHART_TYPES)}"
            }
            return json.dumps(error_dict)

        # Validate data structure
        is_valid, error_msg = validate_chart_data(chart_type, data)
        if not is_valid:
            error_dict = {
                "success": False,
                "error": error_msg,
                "chart_type": chart_type
            }
            return json.dumps(error_dict)

        # Normalize data
        normalized_data = normalize_chart_data(chart_type, data)

        # Convert to Chart.js format based on chart type
        if chart_type in ["bar", "line"]:
            payload = _to_chartjs_bar_line(normalized_data, chart_type, title, x_label, y_label)
        elif chart_type == "area":
            payload = _to_chartjs_area(normalized_data, title, x_label, y_label)
        elif chart_type in ["pie", "doughnut", "polarArea"]:
            payload = _to_chartjs_pie(normalized_data, chart_type, title)
        elif chart_type == "scatter":
            payload = _to_chartjs_scatter(normalized_data, title, x_label, y_label)
        elif chart_type == "bubble":
            payload = _to_chartjs_bubble(normalized_data, title, x_label, y_label)
        elif chart_type == "radar":
            payload = _to_chartjs_radar(normalized_data, title)
        else:
            # Fallback (shouldn't reach here due to validation)
            payload = _to_chartjs_bar_line(normalized_data, "bar", title, x_label, y_label)

        logger.info(f"Created {chart_type} chart with {len(normalized_data)} data points")

        # Return with UI discriminators for inline rendering
        result_dict = {
            "success": True,
            # UI discriminators for frontend inline rendering
            "ui_type": "chart",
            "ui_display": "inline",
            # Chart.js payload
            "payload": payload,
            # Human-readable summary for fallback display
            "summary": f"Created {chart_type} chart '{title}' with {len(normalized_data)} data points"
        }

        return json.dumps(result_dict)

    except Exception as e:
        logger.error(f"Error creating visualization: {e}")
        error_dict = {
            "success": False,
            "error": str(e),
            "chart_type": chart_type
        }
        return json.dumps(error_dict)
