# =============================================================================
# SVG Header Generator - Mojo Implementation
# =============================================================================
#
# Dynamic SVG Header Generator using figlet/toilet fonts.
#
# This tool generates pixel-perfect SVG headers from ASCII art with customizable
# gradient fills. It supports two rendering modes:
#
# 1. PIXEL MODE (default): Converts ASCII art characters to SVG path rectangles.
#    Best for fonts that use simple characters like '#' (e.g., banner3, big).
#
# 2. TEXT MODE (--text-mode): Uses toilet's native SVG export and transforms it.
#    Best for fonts that use Unicode box-drawing characters (e.g., future).
#
# Usage:
#     mojo svg_gen.mojo "Hello" -f banner3 -o header.svg
#     mojo svg_gen.mojo "World" -f future -t -g cyber_cyan
#
# =============================================================================

from collections import List
from collections.string import ord
from pathlib import Path
from sys import argv
from subprocess import run


# =============================================================================
# CONSTANTS
# =============================================================================

alias MAX_TEXT_LENGTH: Int = 1000
alias DEFAULT_SCALE: Int = 10
alias DEFAULT_FONT = "banner3"


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@fieldwise_init
struct GradientStop(Copyable, Movable, Stringable, Writable):
    """
    Immutable gradient color stop for SVG linear gradients.

    A gradient stop defines a color at a specific position along the gradient.
    Multiple stops create smooth color transitions in the final SVG.

    Attributes:
        color: Hex color string in "#RRGGBB" format.
        offset_percent: Position along gradient from 0 (start) to 100 (end).
    """

    var color: String
    var offset_percent: Int

    fn __str__(self) -> String:
        """Return string representation for debugging."""
        return (
            "GradientStop("
            + self.color
            + ", "
            + String(self.offset_percent)
            + "%)"
        )

    fn write_to[W: Writer](self, mut writer: W):
        """Write to a Writer."""
        writer.write(
            "GradientStop(", self.color, ", ", self.offset_percent, "%)"
        )

    fn to_svg(self) -> String:
        """Generate SVG <stop> element for this gradient stop."""
        return (
            '      <stop offset="'
            + String(self.offset_percent)
            + '%" stop-color="'
            + self.color
            + '"/>'
        )


@fieldwise_init
struct GridResult(Copyable, Movable, Stringable, Writable):
    """
    Result from rendering text to an ASCII character grid.

    This is the intermediate representation used in pixel mode.
    The grid contains the raw ASCII art output from toilet/figlet,
    with all lines padded to the same width.

    Attributes:
        lines: List of strings, each representing one row of ASCII art.
        width: Maximum width in characters.
        height: Number of lines in the grid.
    """

    var lines: List[String]
    var width: Int
    var height: Int

    fn __str__(self) -> String:
        """Return string representation for debugging."""
        return (
            "GridResult(" + String(self.width) + "x" + String(self.height) + ")"
        )

    fn write_to[W: Writer](self, mut writer: W):
        """Write to a Writer."""
        writer.write("GridResult(", self.width, "x", self.height, ")")


@fieldwise_init
struct PathResult(Copyable, Movable, Stringable, Writable):
    """
    Result from converting an ASCII grid to SVG path data.

    Contains the SVG path string and dimensions needed to
    construct the final SVG document.

    Attributes:
        path_data: SVG path "d" attribute string containing all rectangles.
        width: Total SVG width in units.
        height: Total SVG height in units.
    """

    var path_data: String
    var width: Int
    var height: Int

    fn __str__(self) -> String:
        """Return string representation for debugging."""
        return (
            "PathResult(" + String(self.width) + "x" + String(self.height) + ")"
        )

    fn write_to[W: Writer](self, mut writer: W):
        """Write to a Writer."""
        writer.write("PathResult(", self.width, "x", self.height, ")")


# =============================================================================
# GRADIENT PRESETS
# =============================================================================


fn get_gradient_stops(preset: String) -> List[GradientStop]:
    """
    Get gradient stops for a named preset.

    Available presets use Dracula theme colors:
        - sweet_dracula: Full rainbow (red -> pink).
        - dracula_purple: Purple -> Pink.
        - cyber_cyan: Cyan -> Green.
        - sunset: Red -> Orange -> Yellow.
        - mono_white: Solid white.

    Args:
        preset: Name of the gradient preset (case-insensitive).

    Returns:
        List of GradientStop objects defining the gradient.
    """
    var stops = List[GradientStop]()

    var name = preset.lower()

    if name == "sweet_dracula":
        # Full rainbow gradient - the default and most colorful option.
        stops.append(GradientStop("#ff5555", 0))  # Red
        stops.append(GradientStop("#ffb86c", 16))  # Orange
        stops.append(GradientStop("#f1fa8c", 33))  # Yellow
        stops.append(GradientStop("#50fa7b", 50))  # Green
        stops.append(GradientStop("#8be9fd", 66))  # Cyan
        stops.append(GradientStop("#bd93f9", 83))  # Purple
        stops.append(GradientStop("#ff79c6", 100))  # Pink
    elif name == "dracula_purple":
        # Purple to pink - elegant two-tone gradient.
        stops.append(GradientStop("#bd93f9", 0))  # Purple
        stops.append(GradientStop("#ff79c6", 100))  # Pink
    elif name == "cyber_cyan":
        # Cyan to green - cool tech/cyber aesthetic.
        stops.append(GradientStop("#8be9fd", 0))  # Cyan
        stops.append(GradientStop("#50fa7b", 100))  # Green
    elif name == "sunset":
        # Red to yellow - warm sunset colors.
        stops.append(GradientStop("#ff5555", 0))  # Red
        stops.append(GradientStop("#ffb86c", 50))  # Orange
        stops.append(GradientStop("#f1fa8c", 100))  # Yellow
    else:
        # Default: mono white (solid color, no gradient effect).
        stops.append(GradientStop("#f8f8f2", 0))
        stops.append(GradientStop("#f8f8f2", 100))

    return stops


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================


fn validate_font_name(font: String) raises:
    """
    Validate font name to prevent command injection and path traversal.

    Only alphanumeric characters, hyphens, and underscores are allowed.

    Args:
        font: Font name to validate.

    Raises:
        Error if font name contains invalid characters.
    """
    for i in range(len(font)):
        var c = ord(font[i])
        var is_valid = (
            (c >= ord("a") and c <= ord("z"))
            or (c >= ord("A") and c <= ord("Z"))
            or (c >= ord("0") and c <= ord("9"))
            or c == ord("-")
            or c == ord("_")
        )
        if not is_valid:
            raise Error(
                "Invalid font name: '"
                + font
                + "'. Only alphanumeric, hyphens, underscores allowed."
            )


fn validate_text(text: String) raises:
    """
    Validate input text for safety and sanity.

    Args:
        text: Text to render.

    Raises:
        Error if text is empty or exceeds maximum length.
    """
    if len(text) == 0:
        raise Error("Text cannot be empty")
    if len(text) > MAX_TEXT_LENGTH:
        raise Error(
            "Text exceeds maximum length of "
            + String(MAX_TEXT_LENGTH)
            + " characters"
        )


# =============================================================================
# CORE RENDERING FUNCTIONS
# =============================================================================


fn render_text_grid(
    text: String, font: String = DEFAULT_FONT
) raises -> GridResult:
    """
    Render text to ASCII character grid using toilet or figlet.

    This is the first step in PIXEL MODE rendering. It calls the external
    toilet program to convert text into ASCII art, then normalizes the
    output into a consistent grid format.

    Args:
        text: The text to convert to ASCII art.
        font: Font name for toilet/figlet.

    Returns:
        GridResult containing ASCII art lines and dimensions.

    Raises:
        Error if validation fails or rendering fails.
    """
    # Security: validate inputs before subprocess call.
    validate_text(text)
    validate_font_name(font)

    # Run toilet to generate ASCII art.
    var cmd = "toilet -f " + font + " -- '" + text + "'"
    var output = run(cmd)

    if len(output) == 0:
        raise Error("No output from toilet for text: '" + text + "'")

    # Split output into lines.
    var lines = List[String]()
    var current_line = String("")
    var max_width = 0

    for i in range(len(output)):
        var c = output[i]
        if c == "\n":
            if len(current_line) > max_width:
                max_width = len(current_line)
            lines.append(current_line)
            current_line = String("")
        else:
            current_line += c

    # Don't forget last line if no trailing newline.
    if len(current_line) > 0:
        if len(current_line) > max_width:
            max_width = len(current_line)
        lines.append(current_line)

    # Pad all lines to equal width.
    var padded_lines = List[String]()
    for i in range(len(lines)):
        var line = lines[i]
        var padding = max_width - len(line)
        var padded = line
        for _ in range(padding):
            padded += " "
        padded_lines.append(padded)

    return GridResult(padded_lines, max_width, len(padded_lines))


fn grid_to_paths(grid: GridResult, scale: Int = DEFAULT_SCALE) -> PathResult:
    """
    Convert ASCII character grid to SVG path data (pixel mode).

    Each non-space character in the ASCII art grid becomes a filled
    rectangle in SVG path format.

    SVG Path Format:
        Each rectangle is encoded as: "M{x},{y}h{w}v{h}h{-w}Z"
        - M = Move to top-left corner.
        - h = Horizontal line (right).
        - v = Vertical line (down).
        - h = Horizontal line (left, negative).
        - Z = Close path (fills the shape).

    Args:
        grid: GridResult from render_text_grid.
        scale: Size of each character cell in SVG units.

    Returns:
        PathResult containing SVG path data and dimensions.
    """
    var path_segments = List[String]()

    # Iterate through each character position in the grid.
    for y in range(grid.height):
        var line = grid.lines[y]
        for x in range(len(line)):
            var c = line[x]

            # Skip whitespace - these become transparent in SVG.
            if c == " ":
                continue

            # Calculate pixel position in SVG coordinates.
            var px = x * scale
            var py = y * scale

            # Generate SVG path for this rectangle.
            # Format: Move to corner, draw right, down, left, close.
            var segment = "M" + String(px) + "," + String(py)
            segment += "h" + String(scale)
            segment += "v" + String(scale)
            segment += "h" + String(-scale)
            segment += "Z"
            path_segments.append(segment)

    # Join all rectangle paths with spaces.
    var path_data = String("")
    for i in range(len(path_segments)):
        if i > 0:
            path_data += " "
        path_data += path_segments[i]

    return PathResult(path_data, grid.width * scale, grid.height * scale)


fn generate_svg(
    path_result: PathResult,
    stops: List[GradientStop],
    gradient_id: String = "headerGradient",
) -> String:
    """
    Generate complete SVG XML document with gradient fill (pixel mode).

    This wraps the path data in a complete SVG document with:
    - XML declaration and SVG namespace.
    - ViewBox for proper scaling.
    - Linear gradient definition in <defs>.
    - Single <path> element filled with gradient.

    Args:
        path_result: PathResult from grid_to_paths.
        stops: List of GradientStop for the gradient.
        gradient_id: XML ID for the gradient definition.

    Returns:
        Complete SVG XML string ready to write to file.
    """
    # Build gradient stops XML.
    var stops_xml = String("")
    for i in range(len(stops)):
        stops_xml += stops[i].to_svg()
        if i < len(stops) - 1:
            stops_xml += "\n"

    # Generate complete SVG document.
    var svg = String('<?xml version="1.0" encoding="UTF-8"?>\n')
    svg += '<svg xmlns="http://www.w3.org/2000/svg"\n'
    svg += (
        '     viewBox="0 0 '
        + String(path_result.width)
        + " "
        + String(path_result.height)
        + '"\n'
    )
    svg += '     width="' + String(path_result.width) + 'px"\n'
    svg += '     height="' + String(path_result.height) + 'px">\n'
    svg += "  <defs>\n"
    svg += (
        '    <linearGradient id="'
        + gradient_id
        + '" x1="0%" y1="0%" x2="100%" y2="0%">\n'
    )
    svg += stops_xml + "\n"
    svg += "    </linearGradient>\n"
    svg += "  </defs>\n"
    svg += (
        '  <path d="'
        + path_result.path_data
        + '" fill="url(#'
        + gradient_id
        + ')"/>\n'
    )
    svg += "</svg>"

    return svg


# =============================================================================
# TEXT MODE RENDERING
# =============================================================================


fn render_text_svg(
    text: String,
    font: String = DEFAULT_FONT,
    owned stops: List[GradientStop] = List[GradientStop](),
    gradient_id: String = "headerGradient",
) raises -> String:
    """
    Render text to SVG using toilet's native SVG export with gradient (text mode).

    This is ideal for fonts that use Unicode box-drawing characters
    (like 'future') where the character shape matters.

    Process:
        1. Call toilet with -E svg flag.
        2. Extract SVG width for gradient coordinates.
        3. Remove black background rectangles.
        4. Inject gradient definition.
        5. Replace text fill colors with gradient reference.

    Args:
        text: The text to convert to SVG.
        font: Font name for toilet.
        stops: List of GradientStop for the gradient.
        gradient_id: XML ID for gradient definition.

    Returns:
        Complete SVG XML string with gradient fill.

    Raises:
        Error if validation fails or toilet fails.
    """
    # Security: validate inputs.
    validate_text(text)
    validate_font_name(font)

    # Use default gradient if none provided.
    if len(stops) == 0:
        stops = get_gradient_stops("sweet_dracula")

    # Run toilet with SVG export.
    var cmd = "toilet -f " + font + " -E svg -- '" + text + "'"
    var svg_content = run(cmd)

    if len(svg_content) == 0:
        raise Error("No output from toilet for text: '" + text + "'")

    # Extract SVG width for gradient coordinates.
    # Look for width="XX" pattern.
    var svg_width = 100  # Default fallback.
    var width_start = svg_content.find('width="')
    if width_start >= 0:
        var num_start = width_start + 7
        var num_end = num_start
        while (
            num_end < len(svg_content)
            and ord(svg_content[num_end]) >= ord("0")
            and ord(svg_content[num_end]) <= ord("9")
        ):
            num_end += 1
        if num_end > num_start:
            var width_str = svg_content[num_start:num_end]
            svg_width = Int(width_str)

    # Build gradient stops XML.
    var stops_xml = String("")
    for i in range(len(stops)):
        stops_xml += stops[i].to_svg()
        if i < len(stops) - 1:
            stops_xml += "\n"

    # Build gradient definition with userSpaceOnUse for absolute coordinates.
    var gradient_def = "  <defs>\n"
    gradient_def += '    <linearGradient id="' + gradient_id + '" '
    gradient_def += 'x1="0" y1="0" x2="' + String(svg_width) + '" y2="0" '
    gradient_def += 'gradientUnits="userSpaceOnUse">\n'
    gradient_def += stops_xml + "\n"
    gradient_def += "    </linearGradient>\n"
    gradient_def += "  </defs>\n"

    # Transform the SVG:
    # 1. Remove black background rectangles (style="fill:#000").
    # 2. Inject gradient definition after <svg> tag.
    # 3. Replace text fill color with gradient reference.

    var result = String("")
    var i = 0

    while i < len(svg_content):
        # Check for <rect with fill:#000.
        if i + 5 < len(svg_content) and svg_content[i : i + 5] == "<rect":
            # Look ahead to see if this rect has fill:#000.
            var rect_end = svg_content.find("/>", i)
            if rect_end > i:
                var rect_content = svg_content[i : rect_end + 2]
                if rect_content.find("fill:#000") >= 0:
                    # Skip this rect.
                    i = rect_end + 2
                    # Skip trailing newline if present.
                    if i < len(svg_content) and svg_content[i] == "\n":
                        i += 1
                    continue

        # Inject gradient def after opening <svg...> tag.
        if i + 4 < len(svg_content) and svg_content[i : i + 4] == "<svg":
            # Find end of svg tag.
            var svg_tag_end = svg_content.find(">", i)
            if svg_tag_end > i:
                result += svg_content[i : svg_tag_end + 1]
                result += "\n" + gradient_def
                i = svg_tag_end + 1
                continue

        # Replace fill:#aaa (or similar) with gradient reference.
        if (
            i + 11 < len(svg_content)
            and svg_content[i : i + 11] == 'style="fill'
        ):
            # Find the closing quote.
            var style_end = svg_content.find('"', i + 7)
            if style_end > i:
                result += 'style="fill:url(#' + gradient_id + ')"'
                i = style_end + 1
                continue

        result += svg_content[i]
        i += 1

    return result


# =============================================================================
# COMMAND LINE INTERFACE
# =============================================================================


fn print_help():
    """Print usage help message."""
    print("SVG Header Generator - Mojo Implementation")
    print("")
    print("Usage: mojo svg_gen.mojo [OPTIONS] TEXT")
    print("")
    print("Arguments:")
    print("  TEXT                    Text to render into ASCII art")
    print("")
    print("Options:")
    print("  -f, --font NAME         Font name for toilet (default: banner3)")
    print("  -o, --output FILE       Output file path (default: stdout)")
    print("  -g, --gradient PRESET   Gradient preset (default: sweet_dracula)")
    print("  -s, --scale N           Pixel scale in SVG units (default: 10)")
    print(
        "  -t, --text-mode         Use toilet SVG text mode (best for 'future'"
        " font)"
    )
    print("  -h, --help              Show this help message")
    print("")
    print("Available gradient presets:")
    print("  sweet_dracula  - Full rainbow (red -> pink)")
    print("  dracula_purple - Purple -> Pink")
    print("  cyber_cyan     - Cyan -> Green")
    print("  sunset         - Red -> Orange -> Yellow")
    print("  mono_white     - Solid white")
    print("")
    print("Examples:")
    print('  mojo svg_gen.mojo "Hello World"')
    print('  mojo svg_gen.mojo "Kitchn" -f future -t -o header.svg')
    print('  mojo svg_gen.mojo "Test" -f banner3 -g cyber_cyan')


fn eprint(msg: String):
    """Print to stderr."""
    from sys.io import FileDescriptor

    print(msg, file=FileDescriptor(2))


fn main() raises:
    """
    Command-line interface entry point.

    Parses arguments and orchestrates the SVG generation process.
    """
    var args = argv()

    # Default values.
    var text = String("")
    var font = String(DEFAULT_FONT)
    var output_path = String("")
    var gradient = String("sweet_dracula")
    var scale = DEFAULT_SCALE
    var text_mode = False

    # Parse arguments.
    var i = 1  # Skip program name.
    while i < len(args):
        var arg = String(args[i])

        if arg == "-h" or arg == "--help":
            print_help()
            return
        elif arg == "-f" or arg == "--font":
            i += 1
            if i < len(args):
                font = String(args[i])
        elif arg == "-o" or arg == "--output":
            i += 1
            if i < len(args):
                output_path = String(args[i])
        elif arg == "-g" or arg == "--gradient":
            i += 1
            if i < len(args):
                gradient = String(args[i])
        elif arg == "-s" or arg == "--scale":
            i += 1
            if i < len(args):
                scale = Int(String(args[i]))
        elif arg == "-t" or arg == "--text-mode":
            text_mode = True
        elif not arg.startswith("-"):
            text = arg

        i += 1

    # Validate required arguments.
    if len(text) == 0:
        print("Error: TEXT argument is required")
        print("Use --help for usage information")
        return

    # Get gradient stops.
    var stops = get_gradient_stops(gradient)

    # Generate SVG.
    var svg: String

    if text_mode:
        # Text mode: use toilet's native SVG export.
        eprint(String("Using text mode with font: ") + font)
        svg = render_text_svg(text, font, stops)
    else:
        # Pixel mode: convert ASCII to path rectangles.
        eprint(String("Using pixel mode with font: ") + font)
        var grid = render_text_grid(text, font)
        eprint("Grid size: " + String(grid.width) + "x" + String(grid.height))

        var path_result = grid_to_paths(grid, scale)
        eprint(
            "SVG size: "
            + String(path_result.width)
            + "x"
            + String(path_result.height)
        )

        svg = generate_svg(path_result, stops)

    # Output.
    if len(output_path) > 0:
        var path = Path(output_path)
        path.write_text(svg)
        eprint("SVG written to " + output_path)
    else:
        print(svg)
