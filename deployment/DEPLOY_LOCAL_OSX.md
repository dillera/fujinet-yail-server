# Local OSX Deployment Guide

## Overview

`deploy_local_osx.py` is a comprehensive deployment script for running the YAIL server locally on macOS. It performs all necessary health checks, validates configuration, and starts the server in foreground mode for easy testing and development.

## Features

✅ **Comprehensive Health Checks**
- Python version verification (3.8+)
- Python module availability
- Required server files
- Environment configuration
- API key validation
- Network connectivity
- Port availability

✅ **Configuration Validation**
- Checks for env file (creates from example if missing)
- Validates API keys (OpenAI or Gemini)
- Verifies model configuration
- Reports any missing dependencies

✅ **Network Detection**
- Automatically detects local IP address
- Reports exact connection details
- Handles both localhost and network connections

✅ **Foreground Execution**
- Server runs in foreground for easy monitoring
- Real-time log output
- Graceful shutdown with Ctrl+C
- Clear connection information for client testing

## Prerequisites

### System Requirements
- macOS (10.14 or later)
- Python 3.8 or later
- pip package manager

### Python Dependencies
The following packages must be installed (see `requirements.txt`):
- Pillow (PIL)
- requests
- python-dotenv
- tqdm
- fastcore
- duckduckgo-search
- google-generativeai (for Gemini support)

### API Keys
At least one of the following:
- **OpenAI API Key** - For DALL-E image generation
- **Gemini API Key** - For Google Gemini image generation

## Installation

### 1. Clone or Navigate to Project

```bash
cd /path/to/fujinet-yail-server
```

### 2. Install Python Dependencies

```bash
cd server
pip install -r requirements.txt
```

Or use a virtual environment (recommended):

```bash
cd server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure API Keys

Create or edit `server/env` file:

```bash
cp deployment/env.example server/env
nano server/env
```

Add your API keys:

```env
# For OpenAI DALL-E
OPENAI_API_KEY=sk-...your-key-here...
GEN_MODEL=dall-e-3

# OR for Google Gemini
GEMINI_API_KEY=your-gemini-key-here
GEN_MODEL=gemini-2.5-pro-exp-03-25
```

## Usage

### Basic Deployment

```bash
cd deployment
python3 deploy_local_osx.py
```

### What Happens

1. **Health Checks** (30 seconds)
   - Verifies Python version
   - Checks all required modules
   - Validates configuration files
   - Confirms API keys are set
   - Tests network connectivity
   - Checks port availability

2. **Server Startup** (5-10 seconds)
   - Loads environment variables
   - Initializes image generation
   - Starts TCP server on port 5556
   - Displays connection information

3. **Foreground Monitoring**
   - Server runs in foreground
   - All logs displayed in real-time
   - Press Ctrl+C to stop gracefully

### Example Output

```
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║      YAIL Server - Local OSX Deployment                ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝

============================================================
YAIL Local OSX Deployment - Health Checks
============================================================

✓ Python 3.8+
✓ Python modules
✓ requirements.txt exists
✓ Server files
✓ Environment file
✓ API configuration: OpenAI API key configured
✓ Network connectivity: Local IP: 192.168.1.100
✓ Port 5556 available

============================================================
Health Check Summary: 8/8 passed
============================================================

✓ All critical checks passed!

============================================================
Starting YAIL Server
============================================================

Command: /usr/bin/python3 /path/to/server/yail.py --loglevel INFO
Working directory: /path/to/server

✓ Server started successfully

============================================================
YAIL Server Ready for Connections
============================================================
Host: 192.168.1.100
Port: 5556
URL: 192.168.1.100:5556
============================================================

Server is running in foreground.
Press Ctrl+C to stop the server.

============================================================

2025-11-06 10:30:45 - yail - INFO - ==================================================
2025-11-06 10:30:45 - yail - INFO - YAIL Server started successfully
2025-11-06 10:30:45 - yail - INFO - Listening on 0.0.0.0:5556
...
```

## Testing the Server

### From Another Terminal

While the server is running, you can test it with the included test scripts:

```bash
# Test image generation
cd deployment
python3 test_gen_command.py "a beautiful sunset over mountains"

# Test image search
python3 test_search_command.py "cats"

# Test with Gemini
python3 test_gemini.py "a robot dancing"
```

### From Atari Emulator

1. Note the IP and port from the deployment output
2. Configure your Atari emulator client to connect to that IP:port
3. Send commands like:
   - `gen a beautiful landscape`
   - `search cats`
   - `camera`
   - `files`
   - `gfx 8` (set graphics mode)

## Troubleshooting

### "Port 5556 already in use"

```bash
# Find process using port 5556
lsof -i :5556

# Kill the process
kill -9 <PID>
```

### "No valid OpenAI API key found"

1. Check `server/env` file exists
2. Verify `OPENAI_API_KEY` is set correctly
3. Ensure key is not wrapped in quotes in the env file

### "Python modules" check fails

```bash
# Install missing modules
pip install -r requirements.txt

# Or with virtual environment
source venv/bin/activate
pip install -r requirements.txt
```

### "Network connectivity" check fails

```bash
# Check internet connection
ping 8.8.8.8

# Try using localhost instead
# Modify the test script to use 127.0.0.1
```

### Server starts but crashes immediately

1. Check the error output in the terminal
2. Verify all required files exist in `server/` directory
3. Check Python version: `python3 --version`
4. Try running with debug logging: 
   ```bash
   python3 server/yail.py --loglevel DEBUG
   ```

## Configuration Options

### Environment Variables

Edit `server/env` to customize:

```env
# Image Generation
OPENAI_API_KEY=your_key_here
GEMINI_API_KEY=your_key_here
GEN_MODEL=dall-e-3              # dall-e-3, dall-e-2, or gemini-*

# DALL-E Configuration
OPENAI_SIZE=1024x1024           # 1024x1024, 1792x1024, 1024x1792
OPENAI_QUALITY=standard         # standard or hd
OPENAI_STYLE=vivid              # vivid or natural
OPENAI_SYSTEM_PROMPT=...        # Custom system prompt
```

### Command-Line Arguments

The server accepts additional arguments:

```bash
python3 server/yail.py \
  --paths /path/to/images \
  --extensions jpg jpeg png \
  --gen-model dall-e-3 \
  --openai-size 1024x1024 \
  --loglevel DEBUG
```

## Monitoring

### Real-Time Logs

All server output is displayed in the terminal:

```
2025-11-06 10:30:45 - yail - INFO - Accepted connection from 192.168.1.50:54321
2025-11-06 10:30:46 - yail - INFO - Starting Connection: 1
2025-11-06 10:30:46 - yail - INFO - Received gen a beautiful sunset
2025-11-06 10:30:50 - yail - INFO - Image generated successfully
2025-11-06 10:30:51 - yail - INFO - Active connections: 0
```

### Connection Information

The deployment script displays:
- **Host**: Local IP address (e.g., 192.168.1.100)
- **Port**: Server port (default: 5556)
- **URL**: Full connection string for clients

## Stopping the Server

Press **Ctrl+C** in the terminal to gracefully shut down:

```
^C
Shutting down server...
Server stopped.
```

## Advanced Usage

### Using Virtual Environment

```bash
cd server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ../deployment
python3 deploy_local_osx.py
```

### With Image Directory

```bash
cd deployment
python3 deploy_local_osx.py --paths ~/Pictures/atari-images
```

### Debug Mode

```bash
# Modify deploy_local_osx.py to use DEBUG level
# Or run server directly with debug
python3 server/yail.py --loglevel DEBUG
```

## Performance Tips

1. **Use SSD**: Image processing is I/O intensive
2. **Adequate RAM**: At least 4GB recommended
3. **Network**: Use wired connection for better stability
4. **API Rate Limits**: Be aware of OpenAI/Gemini rate limits

## Security Notes

⚠️ **Local Development Only**

This deployment is intended for local development and testing:
- Server listens on all interfaces (0.0.0.0)
- No authentication required
- API keys stored in plain text
- Not suitable for production deployment

For production, see `deployment/deploy.sh` for systemd service setup.

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review server logs for error messages
3. Check GitHub issues: https://github.com/dillera/fujinet-yail-server/issues

## Files

- `deploy_local_osx.py` - Main deployment script
- `env.example` - Example environment configuration
- `test_gen_command.py` - Test image generation
- `test_search_command.py` - Test image search
- `test_gemini.py` - Test Gemini generation

## See Also

- `DEPLOY_LOCAL_OSX.md` - This file
- `../server/yail.py` - Main server code
- `../REFACTORING_COMPLETE.md` - Code architecture
- `../THREAD_SAFETY_COMPLETE.txt` - Thread safety improvements
