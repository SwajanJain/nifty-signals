#!/usr/bin/env python3
"""Convert markdown architecture document to PDF."""

import markdown
from weasyprint import HTML, CSS
from pathlib import Path

# Read markdown
md_path = Path(__file__).parent / "SYSTEM_ARCHITECTURE.md"
md_content = md_path.read_text()

# Convert markdown to HTML
html_content = markdown.markdown(
    md_content,
    extensions=['tables', 'fenced_code', 'toc']
)

# Wrap in full HTML with styling for code blocks
full_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Nifty Signals - System Architecture</title>
    <style>
        @page {{
            size: A4;
            margin: 1.5cm;
        }}
        body {{
            font-family: 'Helvetica Neue', Arial, sans-serif;
            font-size: 10pt;
            line-height: 1.4;
            color: #333;
        }}
        h1 {{
            color: #1a1a2e;
            border-bottom: 3px solid #16213e;
            padding-bottom: 10px;
            font-size: 24pt;
        }}
        h2 {{
            color: #16213e;
            border-bottom: 1px solid #e94560;
            padding-bottom: 5px;
            margin-top: 30px;
            font-size: 16pt;
        }}
        h3 {{
            color: #0f3460;
            font-size: 13pt;
        }}
        pre {{
            background-color: #1a1a2e;
            color: #00ff88;
            padding: 15px;
            border-radius: 8px;
            overflow-x: auto;
            font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
            font-size: 7pt;
            line-height: 1.3;
            white-space: pre;
            page-break-inside: avoid;
        }}
        code {{
            background-color: #f0f0f0;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
            font-size: 9pt;
        }}
        pre code {{
            background-color: transparent;
            padding: 0;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 15px 0;
            font-size: 9pt;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background-color: #16213e;
            color: white;
        }}
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        hr {{
            border: none;
            border-top: 2px solid #e94560;
            margin: 30px 0;
        }}
        blockquote {{
            border-left: 4px solid #e94560;
            padding-left: 15px;
            color: #666;
            margin: 15px 0;
        }}
        ul, ol {{
            margin: 10px 0;
            padding-left: 25px;
        }}
        li {{
            margin: 5px 0;
        }}
        .toc {{
            background-color: #f5f5f5;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }}
    </style>
</head>
<body>
{html_content}
</body>
</html>
"""

# Save HTML (for reference)
html_path = Path(__file__).parent / "SYSTEM_ARCHITECTURE.html"
html_path.write_text(full_html)
print(f"HTML saved to: {html_path}")

# Convert to PDF
pdf_path = Path(__file__).parent / "SYSTEM_ARCHITECTURE.pdf"
HTML(string=full_html).write_pdf(pdf_path)
print(f"PDF saved to: {pdf_path}")
