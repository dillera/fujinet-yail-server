# Quick Start - Local OSX Deployment

## 30-Second Setup

### 1. Install Dependencies
```bash
cd server
pip install -r requirements.txt
```

### 2. Configure API Key
```bash
cp deployment/env.example server/env
# Edit server/env and add your OpenAI or Gemini API key
nano server/env
```

### 3. Start Server
```bash
cd deployment
python3 deploy_local_osx.py
```

### 4. Note the IP and Port
The script will display something like:
```
Host: 192.168.1.100
Port: 5556
```

### 5. Connect from Emulator
Use `192.168.1.100:5556` in your Atari emulator client

---

## What the Script Does

✅ Checks Python version (3.8+)
✅ Verifies all required modules installed
✅ Validates API key configuration
✅ Tests network connectivity
✅ Confirms port 5556 is available
✅ Starts server in foreground
✅ Shows exact IP and port for client connection
✅ Displays real-time server logs
✅ Graceful shutdown with Ctrl+C

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Port already in use" | `lsof -i :5556` then `kill -9 <PID>` |
| "No API key found" | Edit `server/env` and add your key |
| "Module not found" | Run `pip install -r requirements.txt` |
| "Connection refused" | Check IP/port from script output |

---

## Test Commands

While server is running, in another terminal:

```bash
# Test image generation
python3 deployment/test_gen_command.py "a sunset"

# Test image search
python3 deployment/test_search_command.py "cats"

# Test Gemini
python3 deployment/test_gemini.py "a robot"
```

---

## Environment Variables

Edit `server/env`:

```env
# OpenAI (DALL-E)
OPENAI_API_KEY=sk-...
GEN_MODEL=dall-e-3

# OR Google Gemini
GEMINI_API_KEY=...
GEN_MODEL=gemini-2.5-pro-exp-03-25

# Optional
OPENAI_SIZE=1024x1024
OPENAI_QUALITY=standard
OPENAI_STYLE=vivid
```

---

## Server Commands

From Atari emulator, send:

```
gen <prompt>           # Generate image
search <terms>         # Search for images
camera                 # Stream webcam
files                  # Stream local image
next                   # Get next image
gfx <mode>            # Set graphics mode (8, 9, 16)
quit                  # Close connection
```

---

## Stop Server

Press **Ctrl+C** in the terminal running the script.

---

## Full Documentation

See `DEPLOY_LOCAL_OSX.md` for complete details.
