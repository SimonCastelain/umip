# Workflows

This directory contains markdown SOPs (Standard Operating Procedures) that define how tasks should be executed.

## Workflow Structure

Each workflow should include:

1. **Objective**: What this workflow accomplishes
2. **Required Inputs**: What data/parameters are needed
3. **Tools Used**: Which scripts in `tools/` to execute
4. **Expected Outputs**: What gets produced and where
5. **Edge Cases**: Common failure modes and how to handle them

## Example

```markdown
# Workflow: Scrape Website

## Objective
Extract structured data from a target website and save to Google Sheets

## Required Inputs
- target_url: The website to scrape
- sheet_id: Google Sheets ID for output

## Tools Used
- tools/scrape_single_site.py
- tools/upload_to_sheets.py

## Expected Outputs
- Raw data in .tmp/scraped_data.json
- Final data in specified Google Sheet

## Edge Cases
- Rate limiting: Add delay between requests
- Invalid URLs: Validate before scraping
- Missing data: Log warnings, continue processing
```

Add your workflows here as you build them.
