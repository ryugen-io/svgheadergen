#!/usr/bin/env python3
"""
Dynamic SVG Header Generator using figlet/toilet fonts.

This tool generates pixel-perfect SVG headers from ASCII art with customizable
gradient fills. It supports two rendering modes:

1. PIXEL MODE (default): Converts ASCII art characters to SVG path rectangles.
   Best for fonts that use simple characters like '#' (e.g., banner3, big).
   Each non-space character becomes a filled rectangle in the SVG.

2. TEXT MODE (--text-mode): Uses toilet's native SVG export and transforms it.
   Best for fonts that use Unicode box-drawing characters (e.g., future, mono9).
   Preserves the actual character shapes with gradient fill applied.

Security features:
- Input validation prevents command injection via font names
- Text length limits prevent resource exhaustion
- Subprocess timeouts prevent hanging
- Safe subprocess handling with shell=False

Usage examples:
    python svg_gen.py "Hello" -f banner3 -o header.svg
    python svg_gen.py "World" -f future --text-mode -g cyber_cyan

Author: Generated with Claude Code
License: MIT
"""

from __future__ import annotations

# =============================================================================
# IMPORTS
# =============================================================================

# Standard library imports for core functionality
import argparse  # CLI argument parsing
import logging  # Structured logging to stderr
import re  # Regular expressions for SVG transformation
import subprocess  # External process execution (toilet/figlet)
import sys  # System exit codes
from dataclasses import dataclass  # Immutable data structures
from enum import Enum  # Gradient preset enumeration
from pathlib import Path  # Cross-platform path handling
from typing import Final, TypeAlias  # Type hints for better code clarity

# =============================================================================
# PUBLIC API EXPORTS
# =============================================================================

__all__ = [
    # Data classes for structured results
    "GradientPreset",  # Built-in gradient color schemes
    "GradientStop",  # Individual gradient color stop
    "GridResult",  # ASCII grid rendering result
    "PathResult",  # SVG path conversion result
    # Exception classes for error handling
    "SVGGeneratorError",  # Base exception for all errors
    # Core rendering functions
    "render_text_grid",  # Render text to ASCII grid (pixel mode)
    "render_text_svg",  # Render text to SVG directly (text mode)
    "grid_to_paths",  # Convert ASCII grid to SVG paths
    "generate_svg",  # Generate final SVG with gradient
]

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

# Configure logging to stderr so SVG output can go to stdout without interference
# Uses simple format: "LEVEL: message" for clean CLI output
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# =============================================================================
# TYPE ALIASES
# =============================================================================

# Type aliases improve code readability by giving semantic meaning to string types
Color: TypeAlias = str  # Hex color string in format "#RRGGBB"
PathData: TypeAlias = str  # SVG path "d" attribute string (e.g., "M0,0h10v10h-10Z")

# =============================================================================
# CONSTANTS
# =============================================================================

# Security: Maximum text length to prevent resource exhaustion attacks
MAX_TEXT_LENGTH: Final[int] = 1000

# Default pixel scale: each ASCII character becomes a 10x10 SVG unit square
DEFAULT_SCALE: Final[int] = 10

# Default font: banner3 is widely available and produces clean block-style output
DEFAULT_FONT: Final[str] = "banner3"

# Security: Font name validation pattern to prevent path traversal attacks
# Only allows alphanumeric characters, hyphens, and underscores
# Prevents inputs like "../../../etc/passwd" or "font;rm -rf /"
FONT_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-zA-Z0-9_-]+$")

# Validation pattern for hex color codes (exactly 6 hex digits after #)
HEX_COLOR_PATTERN: Final[re.Pattern[str]] = re.compile(r"^#[0-9a-fA-F]{6}$")


# =============================================================================
# EXCEPTION CLASSES
# =============================================================================


class SVGGeneratorError(Exception):
    """
    Base exception for all SVG generation errors.

    This is the parent class for all exceptions raised by this module.
    Catching this exception will catch all module-specific errors.
    """


class ValidationError(SVGGeneratorError):
    """
    Raised when input validation fails.

    This includes:
    - Invalid font names (contains disallowed characters)
    - Empty or too-long text input
    - Invalid hex color format
    - Invalid gradient offset percentages
    """


class RenderError(SVGGeneratorError):
    """
    Raised when text rendering fails.

    This includes:
    - toilet/figlet not installed or not found
    - Subprocess execution failures
    - Timeout during rendering
    - Empty output from rendering tool
    """


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass(frozen=True, slots=True)
class GradientStop:
    """
    Immutable gradient color stop for SVG linear gradients.

    A gradient stop defines a color at a specific position along the gradient.
    Multiple stops create smooth color transitions in the final SVG.

    Attributes:
        color: Hex color string in "#RRGGBB" format (e.g., "#ff5555" for red)
        offset_percent: Position along gradient from 0 (start) to 100 (end)

    Example:
        >>> stop = GradientStop("#ff5555", 0)  # Red at the start
        >>> stop = GradientStop("#50fa7b", 100)  # Green at the end
    """

    color: Color
    offset_percent: int

    def __post_init__(self) -> None:
        """
        Validate gradient stop parameters on creation.

        This runs automatically after __init__ due to @dataclass.
        Ensures color format and offset range are valid before use.

        Raises:
            ValidationError: If color format is invalid or offset out of range
        """
        if not HEX_COLOR_PATTERN.match(self.color):
            msg = f"Invalid hex color format: {self.color!r}. Expected #RRGGBB"
            raise ValidationError(msg)
        if not 0 <= self.offset_percent <= 100:
            msg = f"Offset must be 0-100, got {self.offset_percent}"
            raise ValidationError(msg)


class GradientPreset(Enum):
    """
    Built-in gradient presets using Dracula theme colors.

    These presets provide ready-to-use color schemes that look great
    on dark backgrounds (like GitHub dark mode). All colors are from
    the Dracula color palette: https://draculatheme.com/

    Available presets:
        SWEET_DRACULA: Full rainbow gradient (red → orange → yellow → green → cyan → purple → pink)
        DRACULA_PURPLE: Two-color gradient (purple → pink)
        CYBER_CYAN: Two-color gradient (cyan → green)
        SUNSET: Three-color gradient (red → orange → yellow)
        MONO_WHITE: Solid white (no gradient effect)

    Usage:
        >>> gradient = GradientPreset.SWEET_DRACULA
        >>> stops = gradient.stops  # Get the tuple of GradientStop objects
    """

    # Full rainbow gradient - the default and most colorful option
    SWEET_DRACULA = (
        GradientStop("#ff5555", 0),  # Red - Dracula red
        GradientStop("#ffb86c", 16),  # Orange - Dracula orange
        GradientStop("#f1fa8c", 33),  # Yellow - Dracula yellow
        GradientStop("#50fa7b", 50),  # Green - Dracula green
        GradientStop("#8be9fd", 66),  # Cyan - Dracula cyan
        GradientStop("#bd93f9", 83),  # Purple - Dracula purple
        GradientStop("#ff79c6", 100),  # Pink - Dracula pink
    )

    # Purple to pink - elegant two-tone gradient
    DRACULA_PURPLE = (
        GradientStop("#bd93f9", 0),  # Purple - Dracula purple
        GradientStop("#ff79c6", 100),  # Pink - Dracula pink
    )

    # Cyan to green - cool tech/cyber aesthetic
    CYBER_CYAN = (
        GradientStop("#8be9fd", 0),  # Cyan - Dracula cyan
        GradientStop("#50fa7b", 100),  # Green - Dracula green
    )

    # Red to yellow - warm sunset colors
    SUNSET = (
        GradientStop("#ff5555", 0),  # Red - Dracula red
        GradientStop("#ffb86c", 50),  # Orange - Dracula orange
        GradientStop("#f1fa8c", 100),  # Yellow - Dracula yellow
    )

    # Solid white - for when you want no gradient effect
    MONO_WHITE = (
        GradientStop("#f8f8f2", 0),  # Foreground - Dracula foreground
        GradientStop("#f8f8f2", 100),  # Same color = no gradient
    )

    @property
    def stops(self) -> tuple[GradientStop, ...]:
        """
        Return the gradient stops for this preset.

        Returns:
            Tuple of GradientStop objects defining this gradient
        """
        return self.value


@dataclass(frozen=True, slots=True)
class GridResult:
    """
    Result from rendering text to an ASCII character grid.

    This is the intermediate representation used in pixel mode.
    The grid contains the raw ASCII art output from toilet/figlet,
    with all lines padded to the same width.

    Attributes:
        lines: Tuple of strings, each representing one row of the ASCII art
        width: Maximum width in characters (all lines are padded to this)
        height: Number of lines in the grid

    Example:
        For text "Hi" with a simple font, lines might be:
        ("# # ###", "### # #", "# # ###")
    """

    lines: tuple[str, ...]
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class PathResult:
    """
    Result from converting an ASCII grid to SVG path data.

    This contains the SVG path string and dimensions needed to
    construct the final SVG document.

    Attributes:
        path_data: SVG path "d" attribute string containing all rectangles
                   Format: "M0,0h10v10h-10Z M10,0h10v10h-10Z ..."
                   Each "M...Z" segment is one filled rectangle
        width: Total SVG width in units (grid_width * scale)
        height: Total SVG height in units (grid_height * scale)

    SVG Path Commands Used:
        M x,y  = Move to absolute position (x, y)
        h dx   = Horizontal line relative (draw right by dx)
        v dy   = Vertical line relative (draw down by dy)
        Z      = Close path (connects back to start, fills the shape)
    """

    path_data: PathData
    width: int
    height: int


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================


def validate_font_name(font: str) -> None:
    """
    Validate font name to prevent command injection and path traversal attacks.

    This is a critical security function. Font names are passed to subprocess
    calls, so we must ensure they cannot be used for:
    - Path traversal (e.g., "../../../etc/passwd")
    - Command injection (e.g., "font; rm -rf /")
    - Shell metacharacter exploits

    Only alphanumeric characters, hyphens, and underscores are allowed.
    This matches the naming convention used by toilet/figlet fonts.

    Args:
        font: Font name to validate (e.g., "banner3", "future", "mono9")

    Raises:
        ValidationError: If font name contains any disallowed characters

    Example:
        >>> validate_font_name("banner3")  # OK
        >>> validate_font_name("my-font")  # OK
        >>> validate_font_name("../evil")  # Raises ValidationError
    """
    if not FONT_NAME_PATTERN.match(font):
        msg = (
            f"Invalid font name: {font!r}. "
            "Only alphanumeric characters, hyphens, and underscores allowed."
        )
        raise ValidationError(msg)


def validate_text(text: str) -> None:
    """
    Validate input text for safety and sanity.

    Ensures the text:
    - Is not empty (would produce empty output)
    - Does not exceed maximum length (prevents resource exhaustion)

    The text itself is passed to toilet/figlet via subprocess with proper
    argument separation (not shell interpolation), so special characters
    in the text are generally safe. However, length limits prevent
    potential denial-of-service through excessive memory/CPU usage.

    Args:
        text: Text to render into ASCII art

    Raises:
        ValidationError: If text is empty or exceeds MAX_TEXT_LENGTH

    Example:
        >>> validate_text("Hello")  # OK
        >>> validate_text("")  # Raises ValidationError
        >>> validate_text("x" * 2000)  # Raises ValidationError
    """
    if not text:
        raise ValidationError("Text cannot be empty")
    if len(text) > MAX_TEXT_LENGTH:
        msg = f"Text exceeds maximum length of {MAX_TEXT_LENGTH} characters"
        raise ValidationError(msg)


# =============================================================================
# CORE RENDERING FUNCTIONS
# =============================================================================


def render_text_grid(
    text: str,
    font: str = DEFAULT_FONT,
) -> GridResult:
    """
    Render text to ASCII character grid using toilet or figlet.

    This is the first step in PIXEL MODE rendering. It calls the external
    toilet (preferred) or figlet (fallback) program to convert text into
    ASCII art, then normalizes the output into a consistent grid format.

    The function tries toilet first because it has more features and fonts.
    If toilet is not installed, it falls back to figlet which is more
    commonly available on Unix systems.

    Process:
        1. Validate text and font name for security
        2. Try toilet subprocess, fall back to figlet if not found
        3. Capture stdout and split into lines
        4. Pad all lines to equal width (required for grid processing)
        5. Return structured GridResult

    Args:
        text: The text to convert to ASCII art (e.g., "Hello World")
        font: Font name for toilet/figlet (e.g., "banner3", "big", "slant")
              Must match FONT_NAME_PATTERN for security

    Returns:
        GridResult containing:
        - lines: Tuple of equal-length strings (the ASCII art rows)
        - width: Character width of each line
        - height: Number of lines

    Raises:
        ValidationError: If text is empty/too long or font name is invalid
        RenderError: If neither toilet nor figlet is available, or rendering fails

    Example:
        >>> grid = render_text_grid("Hi", "banner3")
        >>> print(grid.width, grid.height)  # e.g., 20, 7
        >>> for line in grid.lines:
        ...     print(line)
    """
    # Security: validate inputs before passing to subprocess
    validate_text(text)
    validate_font_name(font)

    # Try toilet first (more features), then figlet (more common)
    # The "--" separates options from text, preventing text starting with "-"
    # from being interpreted as an option
    commands = [
        ["toilet", "-f", font, "--", text],
        ["figlet", "-f", font, "--", text],
    ]

    last_error: Exception | None = None
    for cmd in commands:
        try:
            # Security: shell=False (default) prevents shell injection
            # capture_output=True captures both stdout and stderr
            # text=True returns strings instead of bytes
            # check=True raises CalledProcessError on non-zero exit
            # timeout=30 prevents hanging on pathological inputs
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            break  # Success - exit the loop
        except FileNotFoundError:
            # This tool not installed, try next one
            last_error = FileNotFoundError(f"{cmd[0]} not found")
            continue
        except subprocess.CalledProcessError as e:
            # Tool returned error (e.g., font not found)
            last_error = e
            continue
        except subprocess.TimeoutExpired as e:
            # Tool took too long - fail immediately, don't try fallback
            msg = f"Command timed out: {' '.join(cmd)}"
            raise RenderError(msg) from e
    else:
        # Loop completed without break = all commands failed
        msg = "Neither toilet nor figlet available or both failed"
        raise RenderError(msg) from last_error

    # Process the ASCII art output
    # Remove trailing newline and split into individual lines
    raw_lines = result.stdout.rstrip("\n").split("\n")

    # Sanity check: ensure we got actual output
    if not raw_lines or all(not line for line in raw_lines):
        msg = f"No output from {cmd[0]} for text: {text!r}"
        raise RenderError(msg)

    # Normalize line lengths by padding shorter lines with spaces
    # This is required because grid_to_paths iterates by (x, y) position
    max_width = max(len(line) for line in raw_lines)
    padded_lines = tuple(line.ljust(max_width) for line in raw_lines)

    return GridResult(
        lines=padded_lines,
        width=max_width,
        height=len(padded_lines),
    )


def grid_to_paths(
    grid: GridResult,
    scale: int = DEFAULT_SCALE,
) -> PathResult:
    """
    Convert ASCII character grid to SVG path data (pixel mode).

    This is the second step in PIXEL MODE rendering. It converts each
    non-space character in the ASCII art grid into a filled rectangle
    in SVG path format.

    The approach is simple but effective:
    - Each character position becomes a potential pixel
    - Space characters are skipped (transparent)
    - All other characters become filled rectangles
    - All rectangles are the same size (scale x scale)

    This works well for fonts that use simple fill characters like '#',
    but loses detail for fonts with varying characters (use text mode
    for those instead).

    SVG Path Format Explanation:
        Each rectangle is encoded as: "M{x},{y}h{w}v{h}h{-w}Z"
        - M{x},{y}  = Move pen to top-left corner (absolute coordinates)
        - h{w}      = Draw horizontal line right by width (relative)
        - v{h}      = Draw vertical line down by height (relative)
        - h{-w}     = Draw horizontal line left by width (relative)
        - Z         = Close path (implicit line to start, triggers fill)

        Example: "M0,0h10v10h-10Z" draws a 10x10 square at origin

    Args:
        grid: GridResult from render_text_grid containing ASCII art lines
        scale: Size of each character cell in SVG units (default: 10)
               Larger scale = larger output SVG

    Returns:
        PathResult containing:
        - path_data: Space-separated SVG path commands for all rectangles
        - width: Total SVG width (grid.width * scale)
        - height: Total SVG height (grid.height * scale)

    Example:
        >>> grid = GridResult(lines=("# #", " # "), width=3, height=2)
        >>> result = grid_to_paths(grid, scale=10)
        >>> # Creates rectangles at (0,0), (20,0), and (10,10)
    """
    # Handle empty grid edge case
    if not grid.lines:
        return PathResult(path_data="", width=0, height=0)

    path_segments: list[str] = []

    # Iterate through each character position in the grid
    for y, line in enumerate(grid.lines):
        for x, char in enumerate(line):
            # Skip whitespace - these become transparent in the SVG
            # Only space is skipped; other whitespace chars become pixels
            if char == " ":
                continue

            # Calculate pixel position in SVG coordinates
            # Each grid cell becomes a (scale x scale) rectangle
            px = x * scale  # X position = column * scale
            py = y * scale  # Y position = row * scale

            # Generate SVG path for this rectangle
            # Format: Move to corner, draw right, down, left, close
            path_segments.append(f"M{px},{py}h{scale}v{scale}h{-scale}Z")

    # Join all rectangle paths with spaces
    # SVG path "d" attribute can contain multiple subpaths separated by spaces
    return PathResult(
        path_data=" ".join(path_segments),
        width=grid.width * scale,
        height=grid.height * scale,
    )


def generate_svg(
    path_result: PathResult,
    gradient: GradientPreset | tuple[GradientStop, ...],
    gradient_id: str = "headerGradient",
) -> str:
    """
    Generate complete SVG XML document with gradient fill (pixel mode).

    This is the final step in PIXEL MODE rendering. It wraps the path data
    from grid_to_paths in a complete SVG document with:
    - XML declaration and SVG namespace
    - ViewBox for proper scaling
    - Linear gradient definition in <defs>
    - Single <path> element with all rectangles, filled with gradient

    The gradient is horizontal (left to right) by default, specified with
    x1="0%" y1="0%" x2="100%" y2="0%". This creates a smooth color transition
    across the entire width of the header.

    SVG Structure:
        <?xml ...?>
        <svg ...>
          <defs>
            <linearGradient id="...">
              <stop offset="0%" stop-color="#..."/>
              <stop offset="100%" stop-color="#..."/>
            </linearGradient>
          </defs>
          <path d="..." fill="url(#...)"/>
        </svg>

    Args:
        path_result: PathResult from grid_to_paths containing path data and dimensions
        gradient: Either a GradientPreset enum value or custom tuple of GradientStop
        gradient_id: XML ID for the gradient definition (default: "headerGradient")
                     Must be unique if embedding multiple SVGs in one document

    Returns:
        Complete SVG XML string ready to write to file or output

    Example:
        >>> path = PathResult(path_data="M0,0h10v10h-10Z", width=100, height=70)
        >>> svg = generate_svg(path, GradientPreset.CYBER_CYAN)
        >>> with open("header.svg", "w") as f:
        ...     f.write(svg)
    """
    # Extract gradient stops from preset enum or use custom tuple directly
    stops = gradient.stops if isinstance(gradient, GradientPreset) else gradient

    # Build the <stop> elements for the gradient definition
    # Each stop specifies a color at a percentage position along the gradient
    stops_xml = "\n".join(
        f'      <stop offset="{stop.offset_percent}%" stop-color="{stop.color}"/>'
        for stop in stops
    )

    # Generate complete SVG document
    # - viewBox defines the coordinate system (0,0 to width,height)
    # - width/height set the default display size
    # - linearGradient with x1=0%, x2=100% creates left-to-right gradient
    # - path element contains all rectangles and references gradient by ID
    svg = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     viewBox="0 0 {path_result.width} {path_result.height}"
     width="{path_result.width}px"
     height="{path_result.height}px">
  <defs>
    <linearGradient id="{gradient_id}" x1="0%" y1="0%" x2="100%" y2="0%">
{stops_xml}
    </linearGradient>
  </defs>
  <path d="{path_result.path_data}" fill="url(#{gradient_id})"/>
</svg>"""

    return svg


def parse_custom_gradient(gradient_str: str) -> tuple[GradientStop, ...]:
    """
    Parse custom gradient from CLI string format.

    Allows users to specify custom gradients via command line without
    modifying code. The format is designed to be easy to type:
        "#color1:offset1,#color2:offset2,..."

    Format Rules:
        - Colors must be hex format: #RRGGBB (6 hex digits)
        - Offsets are integers 0-100 (percentage along gradient)
        - Minimum 2 stops required (start and end)
        - Stops separated by commas
        - Whitespace around colors/offsets is trimmed

    Args:
        gradient_str: Comma-separated color:offset pairs
                      e.g., "#ff0000:0,#00ff00:50,#0000ff:100"

    Returns:
        Tuple of GradientStop objects ready for use with generate_svg

    Raises:
        ValidationError: If format is invalid, colors malformed, or < 2 stops

    Example:
        >>> stops = parse_custom_gradient("#ff0000:0,#0000ff:100")
        >>> len(stops)
        2
        >>> stops[0].color
        '#ff0000'
    """
    stops: list[GradientStop] = []

    # Split by comma and process each color:offset pair
    for part in gradient_str.split(","):
        part = part.strip()

        # Each part must have exactly one colon separating color and offset
        if ":" not in part:
            msg = f"Invalid gradient format: {part!r}. Expected '#color:offset'"
            raise ValidationError(msg)

        # rsplit with maxsplit=1 handles colors that might contain ':'
        # (though valid hex colors won't, this is defensive)
        color, offset_str = part.rsplit(":", 1)

        # Parse offset as integer
        try:
            offset = int(offset_str)
        except ValueError:
            msg = f"Invalid offset value: {offset_str!r}. Must be integer 0-100"
            raise ValidationError(msg) from None

        # GradientStop constructor validates color format and offset range
        stops.append(GradientStop(color.strip(), offset))

    # Gradient needs at least start and end colors
    if len(stops) < 2:
        msg = "Gradient must have at least 2 color stops"
        raise ValidationError(msg)

    return tuple(stops)


# =============================================================================
# TEXT MODE RENDERING
# =============================================================================


def render_text_svg(
    text: str,
    font: str = DEFAULT_FONT,
    gradient: GradientPreset | tuple[GradientStop, ...] = GradientPreset.SWEET_DRACULA,
    gradient_id: str = "headerGradient",
) -> str:
    """
    Render text to SVG using toilet's native SVG export with gradient (text mode).

    This is an alternative to pixel mode that preserves the actual character
    shapes. It's ideal for fonts that use Unicode box-drawing characters
    (like 'future', 'mono9') where the character shape matters.

    How it works:
        1. Call toilet with -E svg flag to get native SVG output
        2. Parse the SVG to extract dimensions
        3. Remove black background rectangles (toilet adds these)
        4. Inject gradient definition into the SVG
        5. Replace text fill colors with gradient reference
        6. Clean up the resulting SVG

    Why gradientUnits="userSpaceOnUse"?
        By default, SVG gradients use "objectBoundingBox" which means the
        gradient is relative to each element's bounding box. This causes
        each character to have its own mini-rainbow effect.

        With "userSpaceOnUse", we specify absolute coordinates (0 to svg_width)
        so the gradient spans the entire SVG. Characters at position 0 get
        the start color, characters at the end get the end color, and
        characters in between get interpolated colors.

    Args:
        text: The text to convert to SVG (e.g., "Hello World")
        font: Font name for toilet (e.g., "future", "mono9")
        gradient: GradientPreset enum value or custom tuple of GradientStop
        gradient_id: XML ID for gradient definition (for embedding multiple SVGs)

    Returns:
        Complete SVG XML string with gradient fill applied to text

    Raises:
        ValidationError: If text or font validation fails
        RenderError: If toilet is not installed or fails

    Note:
        Unlike pixel mode, this requires toilet specifically - figlet does
        not support SVG export. If toilet is not available, use pixel mode.

    Example:
        >>> svg = render_text_svg("Hi", "future", GradientPreset.CYBER_CYAN)
        >>> with open("header.svg", "w") as f:
        ...     f.write(svg)
    """
    # Security: validate inputs before subprocess call
    validate_text(text)
    validate_font_name(font)

    # Run toilet with SVG export mode
    # -E svg: Export format SVG
    # -f font: Use specified font
    # --: End of options (text starting with - won't be misinterpreted)
    try:
        result = subprocess.run(
            ["toilet", "-f", font, "-E", "svg", "--", text],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except FileNotFoundError:
        # toilet not installed - this mode requires toilet specifically
        msg = "toilet not found - required for text mode SVG export"
        raise RenderError(msg) from None
    except subprocess.CalledProcessError as e:
        # toilet returned error (e.g., font not found)
        msg = f"toilet failed: {e.stderr}"
        raise RenderError(msg) from e
    except subprocess.TimeoutExpired as e:
        msg = "toilet command timed out"
        raise RenderError(msg) from e

    svg_content = result.stdout

    # Extract SVG width from the output for gradient coordinate calculation
    # toilet SVG looks like: <svg width="96" height="30" ...>
    width_match = re.search(r'width="(\d+)"', svg_content)
    svg_width = int(width_match.group(1)) if width_match else 100

    # Extract gradient stops from preset or use custom tuple
    stops = gradient.stops if isinstance(gradient, GradientPreset) else gradient

    # Build gradient stop elements
    stops_xml = "\n".join(
        f'      <stop offset="{stop.offset_percent}%" stop-color="{stop.color}"/>'
        for stop in stops
    )

    # Create gradient definition with absolute coordinates
    # gradientUnits="userSpaceOnUse" makes x1/x2 use SVG coordinate system
    # instead of relative to each element's bounding box
    gradient_def = f"""  <defs>
    <linearGradient id="{gradient_id}" x1="0" y1="0" x2="{svg_width}" y2="0" gradientUnits="userSpaceOnUse">
{stops_xml}
    </linearGradient>
  </defs>"""

    # ==========================================================================
    # SVG TRANSFORMATION
    # Transform toilet's SVG output to use our gradient instead of solid colors
    # ==========================================================================

    # Step 1: Remove black background rectangles
    # toilet adds <rect style="fill:#000" .../> for each character cell background
    # We want transparent background, so remove these entirely
    svg_content = re.sub(r'<rect[^>]*style="fill:#000"[^>]*/>\n?', "", svg_content)

    # Step 2: Inject gradient definition after opening <svg> tag
    # Uses regex backreference \1 to preserve the original <svg ...> tag
    svg_content = re.sub(r"(<svg[^>]*>)", r"\1\n" + gradient_def, svg_content)

    # Step 3: Replace text fill color with gradient reference
    # toilet uses style="fill:#aaa" (gray) - we replace with gradient URL
    # Matches 3 or 6 hex digit colors to handle both #rgb and #rrggbb
    svg_content = re.sub(
        r'style="fill:#[0-9a-fA-F]{3,6}"',
        f'style="fill:url(#{gradient_id})"',
        svg_content,
    )

    # Step 4: Remove backdrop rect if present (some toilet versions add this)
    svg_content = re.sub(r'<rect[^>]*class="backdrop"[^>]*/>\n?', "", svg_content)

    # Step 5: Clean up multiple consecutive empty lines left by removals
    # Replace 3+ newlines with just 2 for cleaner output
    svg_content = re.sub(r"\n{3,}", "\n\n", svg_content)

    return svg_content


# =============================================================================
# COMMAND LINE INTERFACE
# =============================================================================


def cli_main() -> int:
    """
    Command-line interface entry point.

    This function handles all CLI argument parsing, validation, and orchestrates
    the SVG generation process. It's designed to be called from __main__ and
    returns an appropriate exit code.

    Exit Codes:
        0   - Success (SVG generated)
        1   - Error (validation failed, rendering failed, etc.)
        130 - Interrupted (Ctrl+C)

    The CLI supports two rendering modes:
        1. Pixel mode (default): Best for simple ASCII fonts like banner3
        2. Text mode (--text-mode): Best for Unicode fonts like future

    Returns:
        Integer exit code for sys.exit()
    """
    # =========================================================================
    # ARGUMENT PARSER SETUP
    # =========================================================================

    parser = argparse.ArgumentParser(
        description="Generate pixel-perfect SVG headers from text using figlet/toilet.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  %(prog)s "Hello World"
  %(prog)s "Kitchn" -f bloody -g sweet_dracula -o header.svg
  %(prog)s "Test" --scale 8 --font banner3
  %(prog)s "Kitchn" -f future --text-mode -o header.svg
  %(prog)s "Custom" --custom-gradient "#ff0000:0,#00ff00:50,#0000ff:100"

Available gradient presets:
  sweet_dracula  - Rainbow (default)
  dracula_purple - Purple → Pink
  cyber_cyan     - Cyan → Green
  sunset         - Red → Orange → Yellow
  mono_white     - Solid white

Modes:
  Default (pixel mode): Converts ASCII art to SVG paths (best for # based fonts)
  --text-mode: Uses toilet SVG export (best for Unicode fonts like 'future')
""",
    )

    parser.add_argument(
        "text",
        nargs="?",
        help="Text to render",
    )
    parser.add_argument(
        "-f",
        "--font",
        default=DEFAULT_FONT,
        metavar="NAME",
        help=f"Font name for toilet/figlet (default: {DEFAULT_FONT})",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        metavar="FILE",
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "-g",
        "--gradient",
        default="sweet_dracula",
        choices=[p.name.lower() for p in GradientPreset],
        metavar="PRESET",
        help="Gradient preset (default: sweet_dracula)",
    )
    parser.add_argument(
        "--custom-gradient",
        metavar="SPEC",
        help="Custom gradient: '#color:offset,...' (e.g., '#ff0000:0,#0000ff:100')",
    )
    parser.add_argument(
        "-s",
        "--scale",
        type=int,
        default=DEFAULT_SCALE,
        metavar="N",
        help=f"Pixel scale in SVG units (default: {DEFAULT_SCALE})",
    )
    parser.add_argument(
        "-t",
        "--text-mode",
        action="store_true",
        help="Use toilet SVG text mode (preserves Unicode chars, best for 'future' font)",
    )
    parser.add_argument(
        "--list-fonts",
        action="store_true",
        help="List available toilet fonts and exit",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    # =========================================================================
    # PARSE AND VALIDATE ARGUMENTS
    # =========================================================================

    args = parser.parse_args()

    # Enable debug logging if --verbose flag is set
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Handle --list-fonts special mode (exits early)
    if args.list_fonts:
        return _list_fonts()

    # Text argument is required unless listing fonts
    if not args.text:
        parser.error("the following arguments are required: text")

    # =========================================================================
    # GENERATE SVG
    # =========================================================================

    try:
        # Determine which gradient to use (custom takes precedence over preset)
        if args.custom_gradient:
            # Parse custom gradient string like "#ff0000:0,#0000ff:100"
            gradient: GradientPreset | tuple[GradientStop, ...] = parse_custom_gradient(
                args.custom_gradient
            )
        else:
            # Look up preset by name (case-insensitive)
            gradient = GradientPreset[args.gradient.upper()]

        # Choose rendering mode based on --text-mode flag
        if args.text_mode:
            # TEXT MODE: Use toilet's native SVG export
            # Best for Unicode fonts like 'future' that use box-drawing characters
            logger.debug("Using text mode with font: %s", args.font)
            svg = render_text_svg(args.text, args.font, gradient)
        else:
            # PIXEL MODE: Convert ASCII art to SVG path rectangles
            # Best for simple fonts like 'banner3' that use # characters
            logger.debug("Using pixel mode with font: %s", args.font)

            # Step 1: Render text to ASCII grid
            grid = render_text_grid(args.text, args.font)
            logger.debug("Grid size: %dx%d characters", grid.width, grid.height)

            # Step 2: Convert grid to SVG paths
            path_result = grid_to_paths(grid, args.scale)
            logger.debug("SVG size: %dx%d units", path_result.width, path_result.height)

            # Step 3: Generate final SVG with gradient
            svg = generate_svg(path_result, gradient)

        # =====================================================================
        # OUTPUT RESULT
        # =====================================================================

        if args.output:
            # Write to file
            args.output.write_text(svg, encoding="utf-8")
            logger.info("SVG written to %s", args.output)
        else:
            # Write to stdout (allows piping: svg_gen.py "Hi" > out.svg)
            print(svg)

        return 0  # Success

    except ValidationError as e:
        # User input was invalid (bad font name, empty text, etc.)
        logger.error("Validation error: %s", e)
        return 1
    except RenderError as e:
        # Rendering failed (toilet/figlet not found, subprocess error, etc.)
        logger.error("Render error: %s", e)
        return 1
    except KeyboardInterrupt:
        # User pressed Ctrl+C
        logger.info("Interrupted")
        return 130  # Standard exit code for SIGINT


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _list_fonts() -> int:
    """
    List available toilet/figlet fonts.

    This helper function is called when --list-fonts is specified.
    It queries toilet for its font directory and lists all available fonts.

    Font files have extensions:
        .tlf - TOIlet font files (toilet-specific)
        .flf - FIGlet font files (compatible with both toilet and figlet)

    Returns:
        0 on success, 1 on error
    """
    try:
        # toilet -I2 returns the font directory path
        # This is a toilet-specific info flag
        result = subprocess.run(
            ["toilet", "-I2"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        font_dir = Path(result.stdout.strip())

        if font_dir.is_dir():
            logger.info("Available fonts in %s:", font_dir)

            # Collect both toilet (.tlf) and figlet (.flf) fonts
            # .stem extracts filename without extension
            fonts = sorted(f.stem for f in font_dir.glob("*.tlf")) + sorted(
                f.stem for f in font_dir.glob("*.flf")
            )

            # Print each font name indented for readability
            for font in fonts:
                print(f"  {font}")
        else:
            logger.warning("Font directory not found: %s", font_dir)

        return 0
    except (subprocess.SubprocessError, OSError) as e:
        logger.error("Failed to list fonts: %s", e)
        return 1


# =============================================================================
# SCRIPT ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    # Run CLI and exit with appropriate code
    sys.exit(cli_main())
