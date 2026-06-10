"""Command-line entry point for the YAIL server."""
import argparse
import logging
import os
import signal
import socket
import sys

from dotenv import load_dotenv

from yail import __version__
from yail.camera import init_camera, shutdown_camera
from yail.config import DEFAULT_EXTENSIONS, DEFAULT_PORT, ImageGenConfig, ServerConfig
from yail.server import YailServer

logger = logging.getLogger("yail")

LOG_LEVELS = ["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"]


def collect_files(paths: list[str], extensions: list[str]) -> list[str]:
    """Collect image file paths from directories and/or explicit file lists."""
    extensions = [ext.lower() if ext.startswith(".") else f".{ext.lower()}"
                  for ext in extensions]
    filenames: list[str] = []

    def consider(file_path: str) -> None:
        _, ext = os.path.splitext(file_path)
        if ext.lower() in extensions:
            logger.info(f"Adding file: {file_path}")
            filenames.append(file_path)

    for path in paths:
        if os.path.isdir(path):
            for root, _, files in os.walk(path):
                for file in files:
                    consider(os.path.join(root, file))
        else:
            consider(path)

    return filenames


def log_network_info() -> None:
    """Log the addresses clients can likely reach this server on."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        logger.info(f"Recommended IP for client connections: {local_ip}")
    except OSError as e:
        logger.warning(f"Could not determine outbound IP: {e}")

    try:
        import netifaces
        for interface in netifaces.interfaces():
            addresses = netifaces.ifaddresses(interface)
            for address in addresses.get(netifaces.AF_INET, []):
                ip = address.get("addr", "")
                if ip and not ip.startswith("127."):
                    logger.info(f"  Interface {interface}: {ip}")
    except ImportError:
        logger.debug("netifaces not installed; skipping interface listing")
    except Exception as e:
        logger.warning(f"Error listing interfaces: {e}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="yail-server", description="YAIL Image Server")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--paths", nargs="*", default=[],
                        help="Directories and/or image files to stream for the 'files' command")
    parser.add_argument("--extensions", nargs="*", default=list(DEFAULT_EXTENSIONS),
                        help="File extensions to include")
    parser.add_argument("--camera", nargs="?", const="", default=None,
                        help="Enable webcam streaming (optionally pass a device name)")
    parser.add_argument("--host", default="0.0.0.0", help="Address to bind (default 0.0.0.0)")
    parser.add_argument("--port", type=int, default=None,
                        help=f"Port to listen on (default {DEFAULT_PORT})")
    parser.add_argument("--loglevel", choices=LOG_LEVELS + [l.lower() for l in LOG_LEVELS],
                        default=None, help="Logging level")
    parser.add_argument("--env-file", default=None,
                        help="Path to an env file (default: ./.env, then legacy ./server/env)")
    parser.add_argument("--openai-api-key", default=None, help="OpenAI API key")
    parser.add_argument("--gen-model", default=None,
                        help="Image generation model (e.g. gpt-image-1, dall-e-3, gemini)")
    parser.add_argument("--openai-size", default=None, help="Image size for generation")
    parser.add_argument("--openai-quality", default=None, help="Image quality for generation")
    parser.add_argument("--openai-style", default=None, help="Image style (dall-e-3 only)")
    return parser


def load_environment(env_file: str | None) -> None:
    """Load env vars. The env file overrides the process environment
    (matching legacy precedence); CLI args override both."""
    if env_file:
        if os.path.exists(env_file):
            logger.info(f"Loading environment variables from {env_file}")
            load_dotenv(env_file, override=True)
        else:
            logger.warning(f"Env file not found: {env_file}")
        return

    for candidate in (".env", os.path.join("server", "env")):
        if os.path.exists(candidate):
            logger.info(f"Loading environment variables from {candidate}")
            load_dotenv(candidate, override=True)
            return
    logger.info("No env file found. Using process environment variables.")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    args = build_parser().parse_args(argv)

    if args.loglevel:
        logging.getLogger().setLevel(args.loglevel.upper())

    load_environment(args.env_file)

    logger.info("Environment:")
    logger.info(f"  OPENAI_API_KEY: {'set' if os.environ.get('OPENAI_API_KEY') else 'not set'}")
    logger.info(f"  GEMINI_API_KEY: {'set' if os.environ.get('GEMINI_API_KEY') else 'not set'}")
    logger.info(f"  GEN_MODEL: {os.environ.get('GEN_MODEL', 'not set (default dall-e-3)')}")

    gen_config = ImageGenConfig()
    if args.openai_api_key:
        gen_config.set_api_key(args.openai_api_key)
    if args.gen_model:
        gen_config.set_model(args.gen_model)
    if args.openai_size:
        gen_config.set_size(args.openai_size)
    if args.openai_quality:
        gen_config.set_quality(args.openai_quality)
    if args.openai_style:
        gen_config.set_style(args.openai_style)
    logger.info(f"Image generation: {gen_config}")

    server_config = ServerConfig(
        host=args.host,
        port=args.port if args.port is not None else int(os.environ.get("YAIL_PORT", DEFAULT_PORT)),
        paths=args.paths,
        extensions=args.extensions,
        camera=args.camera if args.camera else None,
        enable_camera=args.camera is not None,
    )

    filenames = collect_files(server_config.paths, server_config.extensions)
    if filenames:
        logger.info(f"Serving {len(filenames)} local image files")

    if server_config.enable_camera:
        if not init_camera(server_config.camera):
            logger.warning("Camera requested but could not be initialized")

    server = YailServer(server_config, gen_config, filenames)
    try:
        server.bind()
    except OSError as e:
        logger.error(f"Error binding to {server_config.host}:{server_config.port}: {e}")
        logger.error("Port may already be in use. Try killing any existing YAIL processes.")
        return 1

    def signal_handler(sig, frame):
        logger.info("Shutting down YAIL server...")
        shutdown_camera()
        server.shutdown()
        logger.info("YAIL server shutdown complete")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    log_network_info()
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
