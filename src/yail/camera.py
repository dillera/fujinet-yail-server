"""Optional webcam capture via pygame (install with the [camera] extra)."""
import logging

from PIL import Image

from yail.protocol import YAIL_H, YAIL_W

logger = logging.getLogger(__name__)

try:
    import pygame
    import pygame.camera
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

_cam = None


def init_camera(device_name: str | None = None) -> bool:
    """Initialize the camera; returns True on success."""
    global _cam

    if not PYGAME_AVAILABLE:
        logger.warning("Cannot initialize camera: pygame not available "
                       "(pip install 'yail-server[camera]')")
        return False

    try:
        pygame.camera.init()

        if not device_name:
            camera_list = pygame.camera.list_cameras()
            if not camera_list:
                logger.info("No cameras found")
                return False
            device_name = camera_list[0]

        logger.info(f"Using camera: {device_name}")
        _cam = pygame.camera.Camera(device_name, (YAIL_W, YAIL_H))
        _cam.start()
        return True

    except Exception as e:
        logger.error(f"Error initializing camera: {e}")
        return False


def camera_available() -> bool:
    return _cam is not None


def capture_camera_image() -> Image.Image | None:
    """Capture one frame as a PIL image, or None if unavailable."""
    if not _cam:
        logger.error("Cannot capture image: camera not initialized")
        return None

    try:
        img = _cam.get_image()
        img_str = pygame.image.tostring(img, "RGB")
        return Image.frombytes("RGB", img.get_size(), img_str)
    except Exception as e:
        logger.error(f"Error capturing image from camera: {e}")
        return None


def shutdown_camera() -> None:
    global _cam

    if not PYGAME_AVAILABLE:
        return

    try:
        if _cam:
            _cam.stop()
            _cam = None
        pygame.camera.quit()
        logger.info("Camera shutdown complete")
    except Exception as e:
        logger.error(f"Error shutting down camera: {e}")
