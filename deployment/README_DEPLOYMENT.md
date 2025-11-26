# YAIL Server Deployment Guide

## Quick Navigation

### 🚀 **For Local Testing on macOS**
→ **[QUICK_START_LOCAL.md](QUICK_START_LOCAL.md)** (30 seconds)
→ **[DEPLOY_LOCAL_OSX.md](DEPLOY_LOCAL_OSX.md)** (Full guide)

**Command**:
```bash
python3 deploy_local_osx.py
```

### 🖥️ **For Production Deployment (Linux/systemd)**
→ **[deploy.sh](deploy.sh)** (Automated systemd setup)

**Command**:
```bash
sudo bash deploy.sh
```

---

## Deployment Options

### Option 1: Local OSX Development (NEW) ⭐

**Best for**: Testing, development, emulator testing

**Files**:
- `deploy_local_osx.py` - Main deployment script
- `QUICK_START_LOCAL.md` - 30-second quick start
- `DEPLOY_LOCAL_OSX.md` - Full documentation
- `DEPLOY_LOCAL_OSX_SUMMARY.md` - Feature summary

**Features**:
- ✅ Comprehensive health checks
- ✅ Foreground execution with real-time logs
- ✅ Automatic IP detection
- ✅ Clear connection information
- ✅ Graceful shutdown

**Setup Time**: 2-5 minutes

---

### Option 2: Production Linux (Existing)

**Best for**: Production deployment on Linux servers

**Files**:
- `deploy.sh` - Automated systemd service setup
- `fujinet-yail.service` - systemd service file
- `env.example` - Environment template

**Features**:
- ✅ systemd service integration
- ✅ Automatic startup on boot
- ✅ User management
- ✅ Virtual environment setup
- ✅ Dependency installation

**Setup Time**: 5-10 minutes

---

## File Overview

### Deployment Scripts

| File | Purpose | Size | Usage |
|------|---------|------|-------|
| `deploy_local_osx.py` | Local macOS deployment | 13K | `python3 deploy_local_osx.py` |
| `deploy.sh` | Production Linux deployment | 4.3K | `sudo bash deploy.sh` |
| `create_env.py` | Environment file generator | 3.7K | `python3 create_env.py` |

### Documentation

| File | Purpose | Size |
|------|---------|------|
| `QUICK_START_LOCAL.md` | 30-second quick start | 2.3K |
| `DEPLOY_LOCAL_OSX.md` | Complete local guide | 9.5K |
| `DEPLOY_LOCAL_OSX_SUMMARY.md` | Feature summary | 8.0K |
| `README_DEPLOYMENT.md` | This file | - |

### Test Scripts

| File | Purpose | Size |
|------|---------|------|
| `test_gen_command.py` | Test image generation | 2.6K |
| `test_gemini.py` | Test Gemini API | 4.0K |
| `test_image_gen.py` | Test image generation | 3.4K |
| `test_gpt4o.py` | Test GPT-4o | 1.6K |
| `test_server_logs.py` | Monitor server logs | 3.3K |
| `test_service.sh` | Test systemd service | 3.0K |

### Configuration

| File | Purpose |
|------|---------|
| `env.example` | Environment template |
| `fujinet-yail.service` | systemd service definition |

---

## Getting Started

### For Local Testing (macOS)

**1. Install Dependencies**
```bash
cd server
pip install -r requirements.txt
```

**2. Configure API Key**
```bash
cp deployment/env.example server/env
nano server/env  # Add your OpenAI or Gemini API key
```

**3. Start Server**
```bash
cd deployment
python3 deploy_local_osx.py
```

**4. Note the Connection Info**
```
Host: 192.168.1.100
Port: 5556
```

**5. Connect from Emulator**
Use the IP:port in your Atari emulator client

---

### For Production (Linux)

**1. Clone Repository**
```bash
git clone https://github.com/dillera/fujinet-yail-server.git
cd fujinet-yail-server
```

**2. Run Deployment Script**
```bash
sudo bash deployment/deploy.sh
```

**3. Configure Service**
```bash
sudo nano /opt/fujinet-yail-server/server/env
sudo systemctl restart fujinet-yail
```

**4. Check Status**
```bash
sudo systemctl status fujinet-yail
```

---

## Health Checks (Local Deployment)

The `deploy_local_osx.py` script performs these checks:

✅ Python 3.8+ installed
✅ All required Python modules available
✅ requirements.txt exists
✅ All 8 server modules present
✅ Environment file exists/created
✅ API keys configured
✅ Network connectivity
✅ Port 5556 available

If any check fails, the script provides clear error messages and suggestions.

---

## Testing

### Test Image Generation
```bash
python3 deployment/test_gen_command.py "a beautiful sunset"
```

### Test Image Search
```bash
python3 deployment/test_search_command.py "cats"
```

### Test Gemini
```bash
python3 deployment/test_gemini.py "a robot dancing"
```

### From Atari Emulator
Connect to the IP:port and send commands:
```
gen a beautiful landscape
search cats
camera
files
next
gfx 8
quit
```

---

## Configuration

### Environment Variables (server/env)

```env
# Image Generation API Keys
OPENAI_API_KEY=sk-...your-key...
GEMINI_API_KEY=...your-key...

# Model Selection
GEN_MODEL=dall-e-3              # dall-e-3, dall-e-2, or gemini-*

# DALL-E Configuration
OPENAI_SIZE=1024x1024           # 1024x1024, 1792x1024, 1024x1792
OPENAI_QUALITY=standard         # standard or hd
OPENAI_STYLE=vivid              # vivid or natural
OPENAI_SYSTEM_PROMPT='...'      # Custom prompt
```

---

## Troubleshooting

### Port Already in Use
```bash
lsof -i :5556
kill -9 <PID>
```

### No API Key Found
1. Check `server/env` exists
2. Verify API key is set correctly
3. Ensure no quotes around the key

### Python Modules Missing
```bash
pip install -r requirements.txt
```

### Connection Refused
1. Check server is running
2. Verify IP and port from script output
3. Check firewall settings

### Server Crashes
1. Check error output in terminal
2. Verify all server files exist
3. Try with debug logging: `python3 server/yail.py --loglevel DEBUG`

---

## Server Commands

Clients can send these commands:

| Command | Purpose | Example |
|---------|---------|---------|
| `gen` | Generate image | `gen a sunset` |
| `search` | Search images | `search cats` |
| `camera` | Stream webcam | `camera` |
| `files` | Stream local image | `files` |
| `next` | Get next image | `next` |
| `gfx` | Set graphics mode | `gfx 8` |
| `quit` | Close connection | `quit` |

---

## Graphics Modes

| Mode | Name | Resolution | Colors |
|------|------|-----------|--------|
| 8 | GRAPHICS_8 | 320x220 | 2 (B&W dithered) |
| 9 | GRAPHICS_9 | 320x220 | 16 (grayscale) |
| 16 | VBXE | 320x240 | 256 (palette) |

---

## Architecture

```
deployment/
├── deploy_local_osx.py          ← Local macOS deployment
├── deploy.sh                    ← Production Linux deployment
├── QUICK_START_LOCAL.md         ← 30-second quick start
├── DEPLOY_LOCAL_OSX.md          ← Full local guide
├── DEPLOY_LOCAL_OSX_SUMMARY.md  ← Feature summary
├── README_DEPLOYMENT.md         ← This file
├── env.example                  ← Environment template
├── fujinet-yail.service         ← systemd service
├── test_gen_command.py          ← Test image generation
├── test_gemini.py               ← Test Gemini
├── test_image_gen.py            ← Test image gen
├── test_gpt4o.py                ← Test GPT-4o
├── test_server_logs.py          ← Monitor logs
└── test_service.sh              ← Test service
```

---

## Performance

### Local Deployment
- **Startup**: 5-10 seconds
- **Health Checks**: ~2 seconds
- **Memory**: 50-100 MB
- **CPU**: Low (idle), high during generation

### Production Deployment
- **Startup**: ~5 seconds
- **Memory**: 100-200 MB
- **CPU**: Scales with client load
- **Connections**: Supports multiple concurrent clients

---

## Security

### Local Development
- ⚠️ No authentication
- ⚠️ API keys in plain text
- ⚠️ Server listens on all interfaces
- ⚠️ Not for production use

### Production
- ✅ systemd service with user isolation
- ✅ Proper file permissions
- ✅ Environment variables protected
- ✅ Service restart on failure

---

## Support

### Documentation
- `QUICK_START_LOCAL.md` - Quick reference
- `DEPLOY_LOCAL_OSX.md` - Complete guide
- `DEPLOY_LOCAL_OSX_SUMMARY.md` - Features
- `../REFACTORING_COMPLETE.md` - Code architecture
- `../THREAD_SAFETY_COMPLETE.txt` - Thread safety

### Issues
- GitHub: https://github.com/dillera/fujinet-yail-server/issues
- Check logs for error messages
- Use `--loglevel DEBUG` for verbose output

---

## Next Steps

### For Local Testing
1. Read `QUICK_START_LOCAL.md`
2. Run `python3 deploy_local_osx.py`
3. Connect from Atari emulator

### For Production
1. Review `deploy.sh`
2. Run `sudo bash deploy.sh`
3. Configure systemd service
4. Monitor with `systemctl status`

---

## Summary

| Scenario | Script | Time | Docs |
|----------|--------|------|------|
| Local macOS testing | `deploy_local_osx.py` | 5 min | `QUICK_START_LOCAL.md` |
| Production Linux | `deploy.sh` | 10 min | `deploy.sh` comments |
| Quick reference | - | 2 min | `QUICK_START_LOCAL.md` |
| Full guide | - | 20 min | `DEPLOY_LOCAL_OSX.md` |

---

**Last Updated**: November 6, 2025
**Status**: ✅ Ready for use
