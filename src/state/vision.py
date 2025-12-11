"""Vision processing for screen analysis."""

from typing import Dict, Any, List
from PIL import Image, ImageDraw
import numpy as np

from ..utils.logger import get_logger


class VisionProcessor:
    """Processes game screen for visual understanding."""

    # Grid overlay settings
    GRID_SIZE = 16  # Pokemon Red uses 16x16 tiles
    SCREEN_WIDTH = 160
    SCREEN_HEIGHT = 144

    def __init__(self):
        """Initialize vision processor."""
        self.logger = get_logger('Vision')
        self.logger.info("Vision processor initialized")

    def analyze_screen(self, screen_image: Image.Image) -> Dict[str, Any]:
        """Analyze screen image.

        Args:
            screen_image: PIL Image of game screen

        Returns:
            Dict with visual analysis
        """
        # Get grid position (center tile)
        grid_x = (self.SCREEN_WIDTH // 2) // self.GRID_SIZE
        grid_y = (self.SCREEN_HEIGHT // 2) // self.GRID_SIZE

        # Detect screen elements
        elements = self._detect_elements(screen_image)

        # Generate description
        description = self._generate_description(screen_image, elements)

        return {
            'grid_position': (grid_x, grid_y),
            'elements': elements,
            'description': description,
            'screen_size': (screen_image.width, screen_image.height),
        }

    def _detect_elements(self, image: Image.Image) -> List[str]:
        """Detect UI elements on screen.

        Args:
            image: Screen image

        Returns:
            List of detected elements
        """
        elements = []

        # Convert to numpy array for analysis
        img_array = np.array(image)

        # Simple heuristics for element detection
        # Check for text boxes (dark areas at bottom)
        bottom_region = img_array[-40:, :, :]
        if np.mean(bottom_region) < 50:  # Dark region
            elements.append("text_box")

        # Check for menu (white background regions)
        white_pixels = np.sum(np.all(img_array > 200, axis=2))
        total_pixels = img_array.shape[0] * img_array.shape[1]
        if white_pixels / total_pixels > 0.3:
            elements.append("menu")

        # Check for battle (specific color patterns)
        # Pokemon battles have distinctive layouts
        if self._is_battle_screen(img_array):
            elements.append("battle")

        return elements

    def _is_battle_screen(self, img_array: np.ndarray) -> bool:
        """Detect if current screen is a battle.

        Args:
            img_array: Screen image as numpy array

        Returns:
            True if battle screen
        """
        # Check for HP bars (horizontal lines in specific regions)
        # This is a simplified heuristic
        top_region = img_array[:60, :, :]

        # Look for patterns typical in battle screens
        # (This would need more sophisticated detection in production)
        return False  # Placeholder

    def _generate_description(self, image: Image.Image, elements: List[str]) -> str:
        """Generate text description of screen.

        Args:
            image: Screen image
            elements: Detected elements

        Returns:
            Text description
        """
        descriptions = []

        if "battle" in elements:
            descriptions.append("Currently in a Pokemon battle")
        if "menu" in elements:
            descriptions.append("Menu is open")
        if "text_box" in elements:
            descriptions.append("Text box is displayed")

        if not descriptions:
            descriptions.append("Overworld view")

        return "; ".join(descriptions)

    def add_grid_overlay(self, image: Image.Image) -> Image.Image:
        """Add grid overlay to image for visualization.

        Args:
            image: Original image

        Returns:
            Image with grid overlay
        """
        # Create a copy
        img_with_grid = image.copy()
        draw = ImageDraw.Draw(img_with_grid)

        # Draw vertical lines
        for x in range(0, self.SCREEN_WIDTH, self.GRID_SIZE):
            draw.line([(x, 0), (x, self.SCREEN_HEIGHT)], fill=(255, 0, 0), width=1)

        # Draw horizontal lines
        for y in range(0, self.SCREEN_HEIGHT, self.GRID_SIZE):
            draw.line([(0, y), (self.SCREEN_WIDTH, y)], fill=(255, 0, 0), width=1)

        # Highlight center tile
        center_x = (self.SCREEN_WIDTH // 2) // self.GRID_SIZE * self.GRID_SIZE
        center_y = (self.SCREEN_HEIGHT // 2) // self.GRID_SIZE * self.GRID_SIZE

        draw.rectangle(
            [center_x, center_y, center_x + self.GRID_SIZE, center_y + self.GRID_SIZE],
            outline=(0, 255, 0),
            width=2
        )

        return img_with_grid

    def save_annotated_screenshot(self, image: Image.Image, filepath: str) -> None:
        """Save screenshot with annotations.

        Args:
            image: Screen image
            filepath: Path to save image
        """
        annotated = self.add_grid_overlay(image)
        annotated.save(filepath)
        self.logger.debug(f"Saved annotated screenshot to {filepath}")
