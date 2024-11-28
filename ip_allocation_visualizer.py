import csv
import ipaddress
import math
import matplotlib.pyplot as plt
import numpy as np
import logging
import sys
import argparse
from matplotlib.patches import Rectangle

GRID_WIDTH = 256  # Grid width in cells, 2^M
GRID_HEIGHT = 128  # Grid height in cells, 2^N

x_bits = math.ceil(math.log2(GRID_WIDTH))
y_bits = math.ceil(math.log2(GRID_HEIGHT))
max_bits = max(x_bits, y_bits)

def setup_logging():
    """Configure logging for the script."""
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Create handlers
    c_handler = logging.StreamHandler(sys.stdout)
    f_handler = logging.FileHandler('ip_allocation.log')
    c_handler.setLevel(logging.INFO)
    f_handler.setLevel(logging.DEBUG)

    # Create formatters and add to handlers
    c_format = logging.Formatter('%(levelname)s: %(message)s')
    f_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    c_handler.setFormatter(c_format)
    f_handler.setFormatter(f_format)

    # Add handlers to the logger
    if not logger.handlers:
        logger.addHandler(c_handler)
        logger.addHandler(f_handler)

def load_csv(file_path):
    """Load a CSV file and return its rows as a list of dictionaries."""
    try:
        with open(file_path, mode="r", newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            data = list(reader)
            logging.info(f"Loaded {len(data)} records from {file_path}")
            return data
    except FileNotFoundError:
        logging.error(f"File not found: {file_path}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error loading {file_path}: {e}")
        sys.exit(1)

def morton_decode(z):
    x = y = 0
    for i in range(max_bits):
        x |= ((z >> (2 * i)) & 1) << i
        y |= ((z >> (2 * i + 1)) & 1) << i
    return x, y

def decode_offset(offset):
    """
    Decode the IP offset to (x, y) coordinates based on grid dimensions.
    For rectangular grids (GRID_WIDTH == 2 * GRID_HEIGHT), treat as two adjacent square grids.
    """
    if GRID_WIDTH == GRID_HEIGHT:
        x, y = morton_decode(offset)
    elif GRID_WIDTH == 2 * GRID_HEIGHT:
        cells_per_grid = GRID_HEIGHT * (GRID_WIDTH // 2)
        if offset < cells_per_grid:
            x, y = morton_decode(offset)
        else:
            offset_adj = offset - cells_per_grid
            x, y = morton_decode(offset_adj)
            x += GRID_WIDTH // 2
    else:
        raise NotImplementedError("Unsupported grid dimensions. GRID_WIDTH must be equal to GRID_HEIGHT or twice the GRID_HEIGHT.")
    return x, y

def expand_ip_entry(ip_entry):
    """
    Expand an IP entry treating each as a single IP address, ignoring any prefix.
    Returns a list containing a single ipaddress.IPv4Address object.
    """
    ip_field = ip_entry.get("IP Address", "").strip()
    if not ip_field:
        logging.warning("Empty IP Address field encountered.")
        return []

    try:
        # Treat the IP field as a single IP address, ignore any CIDR notation
        ip = ipaddress.IPv4Address(ip_field.split('/')[0])  # Split and take the first part
        return [ip]  # Return as a single-element list
    except ipaddress.AddressValueError:
        logging.error(f"Invalid IP address format: {ip_field}")
        return []
    except Exception as e:
        logging.error(f"Error processing IP '{ip_field}': {e}")
        return []

def extract_ip_details(ip, ip_entry):
    """
    Extract IP details from ip_entry, dynamically including all keys.
    Ensures the IP address is explicitly included as 'IP Address'.

    Args:
        ip (ipaddress.IPv4Address): The IP address object.
        ip_entry (dict): The dictionary representing a row from ip_addresses.csv.

    Returns:
        dict: A dictionary containing all keys from ip_entry, with 'IP Address' explicitly added.
    """
    expected_keys = {
        'Tags': None,
        'Role': None,
        'Status': None,
        'Tenant': None,
    }
    details = {'IP Address': str(ip)}
    details.update(expected_keys)
    details.update(ip_entry)
    return details

def create_allocation_grid(prefix, ip_addresses):
    """
    Create a grid representation for a prefix using Z-order curve.
    Each cell represents a single IP address.
    Returns a dictionary mapping (x, y) to IP details.
    """
    try:
        prefix_obj = ipaddress.IPv4Network(prefix)
        if prefix_obj.prefixlen != 16:
            raise ValueError("Top-level prefix must be /16")
        logging.info(f"Processing prefix: {prefix_obj}")
    except ValueError as ve:
        logging.error(f"Invalid prefix '{prefix}': {ve}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error processing prefix '{prefix}': {e}")
        sys.exit(1)

    grid = np.zeros((GRID_HEIGHT, GRID_WIDTH), dtype=int)
    ip_details = {}  # (x, y): details

    allocated_count = 0
    for idx, ip_entry in enumerate(ip_addresses, start=1):
        expanded_ips = expand_ip_entry(ip_entry)
        if not expanded_ips:
            logging.debug(f"No valid IPs found for entry {idx}")
            continue

        for ip in expanded_ips:
            if ip in prefix_obj:
                offset = int(ip) - int(prefix_obj.network_address)
                x, y = decode_offset(offset)
                if 0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT:
                    grid[y][x] = 1  # Mark as allocated
                    ip_details[(x, y)] = extract_ip_details(ip, ip_entry)  # Changed line
                    allocated_count += 1
                    if allocated_count % 1000 == 0:
                        logging.info(f"Allocated {allocated_count} IPs...")
                else:
                    logging.warning(f"IP {ip} is out of grid bounds.")
            else:
                logging.debug(f"IP {ip} is outside the prefix {prefix_obj}")

    logging.info(f"Total allocated IPs within prefix {prefix_obj}: {allocated_count}")
    return grid, ip_details

def get_prefix_rectangles(top_prefix, prefixes):
    """
    Calculate rectangles representing the sub-prefixes within the top-level /16 prefix.
    Each rectangle is defined by top-left (x1, y1) and bottom-right (x2, y2) coordinates on the grid.
    Returns a list of rectangles with their positions on the grid.
    """
    rectangles = []
    top_network = ipaddress.IPv4Network(top_prefix)

    for prefix_entry in prefixes:
        sub_prefix = prefix_entry.get("Prefix", "").strip()
        if not sub_prefix:
            continue
        try:
            sub_prefix_obj = ipaddress.IPv4Network(sub_prefix)
            if not sub_prefix_obj.subnet_of(top_network):
                continue  # Ignore prefixes outside the top-level /16
            # Calculate offset
            offset_start = int(sub_prefix_obj.network_address) - int(top_network.network_address)
            offset_end = int(sub_prefix_obj.broadcast_address) - int(top_network.network_address)
            # Decode to (x, y)
            x_start, y_start = morton_decode(offset_start)
            x_end, y_end = morton_decode(offset_end)
            # Determine rectangle bounds
            x_min = min(x_start, x_end)
            x_max = max(x_start, x_end)
            y_min = min(y_start, y_end)
            y_max = max(y_start, y_end)
            rectangles.append({
                'x1': x_min,
                'y1': y_min,
                'x2': x_max,
                'y2': y_max,
                'prefix': str(sub_prefix_obj),
                'status': prefix_entry.get('Status'),
                'tenant': prefix_entry.get('Tenant'),
            })
            logging.debug(f"Prefix {sub_prefix_obj} mapped to rectangle: ({x_min},{y_min}) - ({x_max},{y_max})")
        except ipaddress.AddressValueError:
            logging.error(f"Invalid prefix format: {sub_prefix}")
        except Exception as e:
            logging.error(f"Error processing prefix '{sub_prefix}': {e}")
    return rectangles

def design_color_palette():
    """
    Provide examples of color palettes for different roles and statuses.
    Returns a dictionary mapping roles and statuses to colors.
    """
    palette = {
        'roles': {
            'Anycast': '#1f77b4',        # Blue
            'Switch': '#ff7f0e',        # Orange
            'Router': '#2ca02c',        # Green
            'Firewall': '#d62728',      # Red
            'Workstation': '#9467bd',   # Purple
            'Other': '#808080'           # Gray
        },
        'statuses': {
            'Active': '#2ca02c',        # Green
            'Reserved': '#000000',      # Black (with 25% opacity)
            'Inactive': 'none'           # Transparent
        },
        'tags': {
            'Special': '#FF0000'        # Red
        },
        'background': '#ffffff',        # White
        'unallocated': 'none',           # Transparent
        'grid_lines': '#cccccc'         # Light Gray
    }
    return palette

def adjust_color_intensity(hex_color, factor):
    """
    Adjust the intensity of a hex color by a given factor.
    factor < 1: darker, factor > 1: lighter
    """
    if hex_color == 'none':
        return hex_color
    hex_color = hex_color.lstrip('#')
    rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    adjusted = tuple(min(255, max(0, int(c * factor))) for c in rgb)
    return '#{:02x}{:02x}{:02x}'.format(*adjusted)

def blend_colors(color1, color2, alpha):
    """
    Blend two hex colors with a blending coefficient (alpha).
    
    Args:
        color1 (str): The first color in hex format (e.g., '#ff0000').
        color2 (str): The second color in hex format (e.g., '#0000ff').
        alpha (float): The blending coefficient (0.0 to 1.0).
                       0.0 returns color1, 1.0 returns color2.
    
    Returns:
        str: The resulting blended color in hex format.
    """
    if color1 == 'none' or not color1.startswith('#'):
        return color1
    if color2 == 'none' or not color2.startswith('#'):
        raise ValueError(f"Invalid color2: {color2}")
    if not (0.0 <= alpha <= 1.0):
        raise ValueError(f"Alpha must be between 0.0 and 1.0. Given: {alpha}")
    
    color1 = color1.lstrip('#')
    color2 = color2.lstrip('#')
    rgb1 = tuple(int(color1[i:i+2], 16) for i in (0, 2, 4))
    rgb2 = tuple(int(color2[i:i+2], 16) for i in (0, 2, 4))
    
    blended = tuple(
        int((1 - alpha) * c1 + alpha * c2) for c1, c2 in zip(rgb1, rgb2)
    )
    return '#{:02x}{:02x}{:02x}'.format(*blended)

def build_tenant_color_map(ip_addresses, palette):
    """
    Build a mapping from tenant names to color indices using simple modulo division.
    
    Args:
        ip_addresses (list of dict): List of IP address entries from ip_addresses.csv.
        palette (list of str): List of color hex codes.
    
    Returns:
        dict: Mapping of tenant names to color hex codes.
    """
    # Extract unique tenant names, ignoring case and non-alphanumeric characters
    unique_tenants = sorted({
        ''.join(filter(str.isalnum, entry.get('Tenant', '').lower()))
        for entry in ip_addresses
        if entry.get('Tenant', '').strip()
    })
    
    # Assign each tenant a color index based on its position modulo the palette size
    tenant_color_map = {
        tenant: palette[idx % len(palette)] 
        for idx, tenant in enumerate(unique_tenants)
    }
    
    return tenant_color_map

# Predefined Tableau 10 inspired palette (16 colors)
tableau_palette = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728',
    '#9467bd', '#8c564b', '#e377c2', '#7f7f7f',
    '#bcbd22', '#17becf', '#aec7e8', '#ffbb78',
    '#98df8a', '#ff9896', '#c5b0d5', '#c49c94'
]

def get_tenant_color(tenant, tenant_color_map):
    """
    Retrieve the color for a given tenant from the pre-built mapping.
    
    Args:
        tenant (str): The tenant name.
        tenant_color_map (dict): Mapping of tenant names to color hex codes.
    
    Returns:
        str: The color hex code assigned to the tenant.
    """
    # Normalize tenant name: lowercase and remove non-alphanumeric characters
    normalized = ''.join(filter(str.isalnum, tenant.lower()))
    
    # Return the assigned color or default if tenant is unknown
    return tenant_color_map.get(normalized, 'none')

def determine_ip_color(details, palette):
    """
    Determine the color and opacity for an IP address based on its details.
    Returns a tuple of (color, alpha).
    """
    if details['Role'] or details['Tags']:
        return (palette['tags']['Special'], 1.0)  # Deep red for non-empty role or tag
    elif details['Status'] == 'Reserved':
        return ('black', 0.25)  # 25% opaque black for Reserved
    elif details['Status'] == 'Inactive':
        return ('none', 0)  # Transparent for Inactive
    else:
        return ('black', 1)  # Normal

def draw_prefix_rectangles(ax, rectangles, cell_size, tenant_color_map):
    """
    Draw low-contrast prefix rectangles based on tenant.
    """
    for rect_info in rectangles:
        x1 = rect_info['x1'] * cell_size
        y1 = rect_info['y1'] * cell_size
        width = (rect_info['x2'] - rect_info['x1'] + 1) * cell_size
        height = (rect_info['y2'] - rect_info['y1'] + 1) * cell_size
        tenant = rect_info['tenant']
        status = rect_info['status']
        color = get_tenant_color(tenant, tenant_color_map)
        prefix_length = rect_info['prefix'].split('/')[1]
        # if status == "Container":
        #     facecolor = 'none'
        # else:
        #     facecolor = color
        color = blend_colors(color, "#FFFFFF", 0.5)
        ax.add_patch(Rectangle(
            (x1, y1),
            width,
            height,
            edgecolor='black',
            facecolor=color,
            linewidth=0.5,
            linestyle=':',
            # alpha=0.25,
            aa=False,
            zorder=1 + int(prefix_length) if prefix_length else 0
        ))

def draw_sparse_grid(ax, cell_size, palette):
    """
    Draw a sparse 16x16 grid with low-contrast dotted lines.
    """
    for i in range(0, GRID_HEIGHT + 1, 16):
        ax.axhline(i * cell_size, color=palette['grid_lines'], linestyle=':', linewidth=1, zorder=1, aa=False)
    for i in range(0, GRID_WIDTH + 1, 16):
        ax.axvline(i * cell_size, color=palette['grid_lines'], linestyle=':', linewidth=1, zorder=1, aa=False)

def plot_allocated_ips(ax, ip_details, cell_size, palette):
    """
    Plot allocated IP addresses on the grid.
    """
    for (x, y), details in ip_details.items():
        color, alpha = determine_ip_color(details, palette)
        if color != 'none':  # Only plot if not transparent
            rect = Rectangle(
                (x * cell_size + 1, y * cell_size + 1),  # Adjust for spacing
                cell_size - 1,
                cell_size - 1,
                facecolor=color,
                edgecolor='none',
                alpha=alpha,
                aa=False,
                zorder=100 # on top
            )
            ax.add_patch(rect)

def annotate_axes(ax, image_width, image_height, cell_size):
    """
    Annotate the X and Y axes with cell indices.
    """
    ax.set_xlabel('X-axis (0-255)', fontsize=12)
    ax.set_ylabel('Y-axis (0-255)', fontsize=12)

    # Set tick positions based on cell indices
    x_ticks = range(0, image_width, 16 * cell_size)
    y_ticks = range(0, image_height, 16 * cell_size)

    ax.set_xticks(x_ticks)
    ax.set_yticks(y_ticks)

    # Set tick labels to cell indices
    ax.set_xticklabels([str(i) for i in range(0, GRID_WIDTH, 16)])
    ax.set_yticklabels([str(i) for i in range(0, GRID_HEIGHT, 16)])

    # Remove tick marks
    ax.tick_params(axis='both', which='both', length=0)

def finalize_plot(ax, image_width, image_height):
    """
    Finalize plot settings.
    """
    ax.set_xlim(0, image_width)
    ax.set_ylim(0, image_height)
    ax.invert_yaxis()  # To have (0,0) at top-left
    fig = ax.get_figure()
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    plt.title("IP Address Allocation", pad=10)

def plot_allocation_grid(grid, ip_details, rectangles, palette, output_file, cell_size, tenant_color_map):
    """Visualize the allocation grid and save it as a PNG."""
    try:
        image_width = GRID_WIDTH * cell_size
        image_height = GRID_HEIGHT * cell_size
        fig, ax = plt.subplots(figsize=(image_width / 100, image_height / 100), dpi=100)

        # Set background
        ax.set_facecolor(palette['background'])

        # Draw sparse 16x16 grid lines with low contrast dotted lines
        draw_sparse_grid(ax, cell_size, palette)

        # Annotate axes with cell indices
        annotate_axes(ax, image_width, image_height, cell_size)

        # Draw prefix rectangles with low contrast based on tenant
        draw_prefix_rectangles(ax, rectangles, cell_size, tenant_color_map)

        # Plot each allocated IP
        plot_allocated_ips(ax, ip_details, cell_size, palette)

        # Finalize and save the plot
        finalize_plot(ax, image_width, image_height)

        plt.savefig(output_file, dpi=100, bbox_inches='tight', pad_inches=0)
        plt.close()
        logging.info(f"Allocation grid saved to {output_file}")
    except Exception as e:
        logging.error(f"Error saving the allocation grid image: {e}")
        sys.exit(1)

def get_top_level_prefix(prefixes):
    """
    Extract the first valid /16 prefix from the prefixes list.

    Args:
        prefixes (list of dict): List of prefixes loaded from the prefixes CSV file.

    Returns:
        tuple: A tuple containing the selected top-level /16 prefix (str) and its IPv4Network object.

    Raises:
        ValueError: If no valid /16 prefix is found.
    """
    for prefix_entry in prefixes:
        prefix = prefix_entry.get("Prefix", "").strip()
        if not prefix:
            logging.warning("Empty Prefix field encountered in prefixes file.")
            continue
        try:
            prefix_obj = ipaddress.IPv4Network(prefix)
            if prefix_obj.prefixlen == 16:
                logging.info(f"Selected top-level /16 prefix: {prefix}")
                return prefix, prefix_obj
        except ipaddress.AddressValueError:
            logging.error(f"Invalid prefix format: {prefix}")
        except Exception as e:
            logging.error(f"Error processing prefix '{prefix}': {e}")

    raise ValueError("No valid /16 prefix found in the prefixes file.")

def parse_arguments():
    parser = argparse.ArgumentParser(description="Generate IP Address Allocation Grid Image.")
    parser.add_argument(
        "-p", "--prefixes",
        type=str,
        default="prefixes.csv",
        help="Path to the prefixes CSV file."
    )
    parser.add_argument(
        "-i", "--ip_addresses",
        type=str,
        default="ip_addresses.csv",
        help="Path to the IP addresses CSV file."
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="allocation_grid.png",
        help="Output PNG file name."
    )
    parser.add_argument(
        "-c", "--cell_size",
        type=int,
        default=4,
        help="Size of each grid cell in pixels. Default is 4."
    )

    args = parser.parse_args()
    return args

def main():
    args = parse_arguments()
    prefixes_file = args.prefixes
    ip_addresses_file = args.ip_addresses
    output_file = args.output
    cell_size = args.cell_size

    setup_logging()
    logging.info("Starting IP Address Allocation Visualization Script")

    prefixes = load_csv(prefixes_file)
    ip_addresses = load_csv(ip_addresses_file)

    tenant_color_map = build_tenant_color_map(prefixes, tableau_palette)

    try:
        top_level_prefix, top_prefix_obj = get_top_level_prefix(prefixes)
    except ValueError as e:
        logging.error(e)
        sys.exit(1)

    # Create a grid for IP allocation
    grid, ip_details = create_allocation_grid(top_level_prefix, ip_addresses)

    # Get rectangles for prefixes
    prefix_rectangles = get_prefix_rectangles(top_level_prefix, prefixes)

    # Design color palette
    palette = design_color_palette()

    # Plot and save the allocation grid
    plot_allocation_grid(grid, ip_details, prefix_rectangles, palette, output_file, cell_size, tenant_color_map)
    logging.info("Script completed successfully.")

if __name__ == "__main__":
    main()