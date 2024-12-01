# Functional Specification: IP Address Allocation Visualization Script

## 1. Purpose
The IP Address Allocation Visualization Script is designed to generate a visual representation of IP address allocations within a specified network prefix. It processes input data from CSV files containing network prefixes and IP address details, and outputs a color-coded PNG image that illustrates the distribution and categorization of IP addresses on a configurable grid.

## 2. Scope
- **In-Scope**: 
  - Loading and processing network prefix and IP address data from CSV files.
  - Mapping IP addresses to grid coordinates using a Z-order (Morton) curve.
  - Assigning colors based on tenants, roles, statuses, and tags.
  - Generating a PNG image that visually represents IP allocations with grid lines and annotations.
  - Supporting configurable grid dimensions and cell sizes.
  - Logging operations and handling errors gracefully.
  
- **Out-of-Scope**: 
  - Interactive or dynamic visualization features.
  - Real-time data updates or integrations with external systems.

## 3. Inputs
- **Prefixes CSV File**:
  - Contains network prefixes and associated tenant information.
  - Essential Fields:
    - `Prefix`: Network prefix in CIDR notation (e.g., `192.168.0.0/16`).
    - `Tenant`: Name of the tenant associated with the prefix.
  - Additional arbitrary fields may be present.

- **IP Addresses CSV File**:
  - Contains individual IP addresses and their attributes.
  - Essential Fields:
    - `IP Address`: Individual IP address (ignores any CIDR notation).
  - Optional Fields:
    - `Tags`: Tags associated with the IP address.
    - `Role`: Role designation (e.g., `Router`, `Switch`).
    - `Status`: Allocation status (`Active`, `Reserved`, `Inactive`).
    - `Tenant`: Name of the tenant associated with the IP address.
  - Additional arbitrary fields may be present.

## 4. Outputs
- **Allocation Grid PNG Image**:
  - A PNG image that visually represents the allocation of IP addresses on a grid.
  - Features:
    - Color-coded cells based on tenant, role, status, and tags.
    - Grid lines to delineate cell boundaries.
    - Annotations for axis indices.
    - Highlighted rectangles representing sub-prefix regions.

## 5. Functional Requirements

### 5.1 Data Loading
- **Load Prefixes**:
  - Read and parse the prefixes CSV file.
  - Validate the format of network prefixes.
  
- **Load IP Addresses**:
  - Read and parse the IP addresses CSV file.
  - Validate the format of IP addresses.

### 5.2 Prefix Selection
- **Top-Level Prefix**:
  - Identify and select the first valid top-level network prefix (e.g., `/16`) from the prefixes data.
  - Ensure the selected prefix is suitable for grid mapping.

### 5.3 Grid Configuration
- **Grid Dimensions**:
  - Support configurable grid width and height, both being integer powers of 2.
  - Supported Aspect Ratios:
    - 1:1 (Square Grid): Width equals Height.
    - 2:1 (Rectangular Grid): Width is twice the Height.
  
- **Cell Size**:
  - Allow configuration of cell size in pixels.
  - Ensure cells are square and maintain consistent spacing.

### 5.4 IP Mapping and Allocation
- **Z-order Mapping**:
  - Map each IP address to grid coordinates using a Z-order (Morton) curve.
  - Handle both square and rectangular grid mappings appropriately.
  
- **Grid Allocation**:
  - Mark allocated IPs on the grid.
  - Ensure that IPs outside the selected prefix are ignored or logged.

### 5.5 Color Assignment
- **Tenant Color Mapping**:
  - Pre-build a mapping from tenant names to specific colors using simple modulo division based on a predefined color palette.
  - Normalize tenant names by converting to lowercase and removing non-alphanumeric characters.
  - Assign a default color for unknown tenants.
  
- **IP Color Determination**:
  - Assign colors to IP addresses based on the following criteria:
    - If `Role` or `Tags` are present: Assign a special color.
    - If `Status` is `Reserved`: Assign a semi-transparent black.
    - If `Status` is `Inactive`: Assign transparency.
    - Otherwise: Assign the default tenant color.

### 5.6 Visualization
- **Grid Lines**:
  - Draw sparse grid lines (e.g., every 16 cells) with low contrast.
  - Ensure grid lines are rendered beneath painted cells.
  
- **Prefix Rectangles**:
  - Highlight regions of sub-prefixes with distinct colors based on tenant assignments.
  - Maintain low opacity to keep grid lines visible.
  
- **IP Cells**:
  - Paint allocated IP addresses on the grid with assigned colors.
  - Ensure proper alignment and spacing to prevent overlap with grid lines.
  
- **Axis Annotations**:
  - Label X and Y axes with cell indices.
  - Ensure annotations do not obscure painted cells.

### 5.7 Image Generation
- **Image Sizing**:
  - Calculate image dimensions based on grid size and cell size.
  - Ensure precise sizing to avoid blurring.
  
- **Rendering Order**:
  - Render elements in the following order to maintain visual hierarchy:
    1. Grid lines
    2. Axis annotations
    3. Prefix rectangles
    4. IP cells

### 5.8 Logging and Error Handling
- **Logging**:
  - Provide informational logs for general operations (e.g., data loading, progress updates).
  - Provide debug logs for detailed diagnostics (e.g., invalid entries, allocation counts).
  
- **Error Handling**:
  - Gracefully handle missing or malformed data fields.
  - Log errors and warnings without interrupting the entire process unless critical.

### 5.9 Command-Line Interface
- **Arguments**:
  - `--prefixes` (`-p`): Path to the prefixes CSV file.
  - `--ip_addresses` (`-i`): Path to the IP addresses CSV file.
  - `--output` (`-o`): Output PNG file name.
  - `--cell_size` (`-c`): Size of each grid cell in pixels.
  
- **Defaults**:
  - Provide default values for all command-line arguments to facilitate ease of use.

## 6. Non-Functional Requirements

### 6.1 Performance
- Efficiently handle large datasets and large grid sizes without significant performance degradation.
  
### 6.2 Usability
- Provide clear and concise logging messages for monitoring and troubleshooting.
- Ensure the script can be easily executed with minimal setup.

### 6.3 Maintainability
- Modularize code by separating distinct functionalities into helper functions.
- Replace magic numbers with defined constants for easier configuration.
- Adhere to coding best practices to facilitate future enhancements and debugging.

### 6.4 Extensibility
- Allow easy adjustment of grid dimensions within supported aspect ratios.
- Enable expansion of color palettes and tenant mappings without major code changes.
- Support additional attributes in input data for future feature additions.

## 7. Constraints and Preconditions
- **Grid Dimensions**:
  - `GRID_WIDTH` and `GRID_HEIGHT` must be integer powers of 2.
  - Supported Aspect Ratios:
    - 1:1 (Square Grid)
    - 2:1 (Rectangular Grid: `GRID_WIDTH` equals `2 * GRID_HEIGHT`)
  
- **Data Integrity**:
  - IP entries must contain a valid `IP Address` field.
  - Prefix entries must contain a valid `Prefix` field with a `/16` prefix length.

- **Color Palette**:
  - The predefined palette should adequately cover the expected number of tenants to minimize color repetition.

## 8. Assumptions
- Input CSV files are well-formatted and contain the necessary fields.
- The first valid `/16` prefix in the prefixes CSV is the target for visualization.
- The number of unique tenants does not exceed the capacity of the predefined color palette.

## 9. Dependencies
- **Programming Language**: Python 3.6+
- **Libraries**:
  - `csv`
  - `ipaddress`
  - `math`
  - `matplotlib`
  - `numpy`
  - `logging`
  - `argparse`
  - `collections.defaultdict`

## 10. Future Enhancements
- Support for additional grid aspect ratios beyond 1:1 and 2:1.
- Interactive visualization features (e.g., zooming, tooltips).
- Integration with real-time data sources for dynamic updates.
- Enhanced color mapping strategies to accommodate a larger number of tenants without color repetition.
