# Tools

This directory contains Python scripts that perform deterministic execution tasks.

## Tool Guidelines

1. **Single Responsibility**: Each tool should do one thing well
2. **Use Environment Variables**: Load API keys from .env using python-dotenv
3. **Clear Error Messages**: Make failures easy to diagnose
4. **Accept Arguments**: Use argparse or similar for CLI arguments
5. **Log Actions**: Print what you're doing for transparency

## Example Tool Structure

```python
#!/usr/bin/env python3
"""
Tool: Example Tool
Purpose: Brief description of what this tool does
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    """Main execution function"""
    # Your code here
    pass

if __name__ == "__main__":
    main()
```

## Testing

Test your tools independently before integrating them into workflows:

```bash
python tools/your_tool.py --arg value
```

Add your tools here as you build them.
