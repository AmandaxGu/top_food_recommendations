from pathlib import Path
import pandas as pd
import pydeck as pdk
import streamlit as st

from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import Request, urlopen
import re


# ---------------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------------

st.set_page_config(
    page_title="My Food Spots",
    layout="wide"
)

st.markdown(
    """
    <style>
    :root {
        --bg: #0E1117;
        --panel: #161B22;
        --field: #20262E;
        --border: #30363D;
        --text: #F4F7FA;
        --muted: #C5CDD6;
        --accent: #C1FD3B;
        --accent-hover: #A9E92F;
    }

    /* Top header */
    [data-testid="stHeader"],
    [data-testid="stToolbar"] {
        background: var(--bg) !important;
    }

    [data-testid="stDecoration"] {
        display: none !important;
    }

    /* Sidebar open/close arrows */
    [data-testid="stSidebarCollapseButton"] svg,
    [data-testid="stSidebarCollapsedControl"] svg {
        color: var(--text) !important;
        fill: var(--text) !important;
        stroke: var(--text) !important;
    }

    [data-testid="stSidebarCollapseButton"] button:hover svg,
    [data-testid="stSidebarCollapsedControl"] button:hover svg {
        color: var(--accent) !important;
        fill: var(--accent) !important;
        stroke: var(--accent) !important;
    }

    /* Form inputs */
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input {
        background: var(--field) !important;
        color: var(--text) !important;
        border-color: var(--border) !important;
        caret-color: var(--accent) !important;
    }

    input::placeholder {
        color: var(--muted) !important;
        opacity: 1 !important;
    }

    /* Primary buttons */
    button[kind="primary"],
    [data-testid="stFormSubmitButton"] button {
        background: var(--accent) !important;
        color: var(--bg) !important;
        border-color: var(--accent) !important;
        font-weight: 700 !important;
    }

    button[kind="primary"]:hover,
    [data-testid="stFormSubmitButton"] button:hover {
        background: var(--accent-hover) !important;
        border-color: var(--accent-hover) !important;
    }

    /* Secondary/download buttons */
    button[kind="secondary"],
    [data-testid="stDownloadButton"] button {
        background: var(--panel) !important;
        color: var(--text) !important;
        border: 1px solid var(--accent) !important;
    }

    /* Expanders */
    [data-testid="stExpander"] {
        background: var(--panel) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
    }

    [data-testid="stExpander"] summary {
        background: var(--panel) !important;
        border-radius: 8px !important;
    }

    [data-testid="stExpander"] summary p,
    [data-testid="stExpander"] summary span,
    [data-testid="stExpander"] summary svg {
        color: var(--text) !important;
        fill: var(--text) !important;
    }

    /* Expander hover */
    [data-testid="stExpander"] summary:hover {
        background: var(--field) !important;
    }

    [data-testid="stExpander"] summary:hover p,
    [data-testid="stExpander"] summary:hover span,
    [data-testid="stExpander"] summary:hover svg {
        color: var(--accent) !important;
        fill: var(--accent) !important;
    }

    /* Global accents */
    a {
        color: var(--accent) !important;
    }

    *:focus-visible {
        outline-color: var(--accent) !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <h1 style="
        color: #FFFFFF;
        margin-bottom: 0;
    ">
        Top <span style="color:#C1FD3B;"> Food Spots </span>
    </h1>

    <p style="
        color: #AEB6C2;
        margin-top: 4px;
        margin-bottom: 25px;
        font-size: 16px;
    ">
        Explore, filter, and add your favorite places.
    </p>
    """,
    unsafe_allow_html=True
)


# Display a success message after Streamlit reruns
if "location_added_message" in st.session_state:
    st.success(st.session_state.location_added_message)
    del st.session_state.location_added_message

# ---------------------------------------------------------
# FILE PATHS
# ---------------------------------------------------------

# Folder containing this Streamlit script
APP_FOLDER = Path(__file__).resolve().parent

# Data subfolder visible in the GitHub repository
DATA_FOLDER = APP_FOLDER / "data"

BASE_FILE = DATA_FOLDER / "food_loc_exact.xlsx"
USER_LOCATIONS_FILE = DATA_FOLDER / "user_added_locations.csv"

# ---------------------------------------------------------
# REQUIRED COLUMNS
# ---------------------------------------------------------

USER_LOCATION_COLUMNS = [
    "Location Name",
    "Brief Description",
    "Region Hint",
    "Latitude",
    "Longitude",
    "Coordinate Confidence / Basis",
    "Added By User"
]

# ---------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------

@st.cache_data
def load_base_locations():
    df = pd.read_excel(BASE_FILE)

    df["Latitude"] = pd.to_numeric(
        df["Latitude"],
        errors="coerce"
    )

    df["Longitude"] = pd.to_numeric(
        df["Longitude"],
        errors="coerce"
    )

    df = df.dropna(
        subset=["Latitude", "Longitude"]
    ).copy()

    return df


def load_user_locations():
    """
    Load previously added locations if the CSV exists.

    If the CSV does not exist yet, return an empty dataframe.
    The CSV will be created automatically when the first
    location is successfully added.
    """

    if USER_LOCATIONS_FILE.exists():
        additions = pd.read_csv(USER_LOCATIONS_FILE)

        # Ensure all expected columns exist
        for column in USER_LOCATION_COLUMNS:
            if column not in additions.columns:
                additions[column] = None

        additions["Latitude"] = pd.to_numeric(
            additions["Latitude"],
            errors="coerce"
        )

        additions["Longitude"] = pd.to_numeric(
            additions["Longitude"],
            errors="coerce"
        )

        additions["Added By User"] = True

        additions = additions.dropna(
            subset=["Latitude", "Longitude"]
        ).copy()

        return additions[USER_LOCATION_COLUMNS]

    return pd.DataFrame(
        columns=USER_LOCATION_COLUMNS
    )


base_df = load_base_locations()

# Initialize user-added data once per browser session
if "user_locations" not in st.session_state:
    st.session_state.user_locations = load_user_locations()

# ---------------------------------------------------------
# GOOGLE MAPS URL PARSING
# ---------------------------------------------------------

def resolve_google_maps_url(url):
    """
    Expand shortened Google Maps URLs such as maps.app.goo.gl.

    Full Google Maps URLs are returned unchanged.
    """
    clean_url = url.strip()

    if not clean_url:
        raise ValueError("Enter a Google Maps URL.")

    parsed_url = urlparse(clean_url)

    if parsed_url.scheme not in {"http", "https"}:
        raise ValueError(
            "The Google Maps URL must begin with http:// or https://."
        )

    hostname = parsed_url.netloc.lower()

    allowed_google_hosts = (
        "google.com",
        "www.google.com",
        "maps.google.com",
        "maps.app.goo.gl",
        "goo.gl",
    )

    is_google_url = any(
        hostname == host or hostname.endswith(f".{host}")
        for host in allowed_google_hosts
    )

    if not is_google_url:
        raise ValueError(
            "Enter a URL copied from Google Maps."
        )

    # Shortened URLs need to be expanded before parsing.
    if hostname in {"maps.app.goo.gl", "goo.gl"}:
        request = Request(
            clean_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 AppleWebKit/537.36 "
                    "Chrome/120.0 Safari/537.36"
                )
            }
        )

        try:
            with urlopen(request, timeout=10) as response:
                return response.geturl()

        except Exception as error:
            raise ValueError(
                "The shortened Google Maps URL could not be expanded. "
                "In Google Maps, use Share > Copy link and try again. "
                f"Technical detail: {error}"
            ) from error

    return clean_url


def clean_google_place_name(raw_name):
    """
    Convert a Google Maps URL name into readable text.
    """
    if not raw_name:
        return None

    clean_name = unquote(raw_name)

    clean_name = clean_name.replace("+", " ")
    clean_name = clean_name.replace("_", " ")

    # Remove repeated whitespace.
    clean_name = re.sub(r"\s+", " ", clean_name).strip()

    return clean_name or None


def extract_name_from_google_url(url):
    """
    Extract a place name from common Google Maps URL formats.
    """
    decoded_url = unquote(url)
    parsed_url = urlparse(decoded_url)
    query_parameters = parse_qs(parsed_url.query)

    # Most common format:
    # google.com/maps/place/PLACE+NAME/@latitude,longitude,...
    place_match = re.search(
        r"/maps/(?:place|search)/([^/@?]+)",
        decoded_url,
        flags=re.IGNORECASE
    )

    if place_match:
        possible_name = clean_google_place_name(
            place_match.group(1)
        )

        if possible_name:
            return possible_name

    # Some URLs store the place/search name in query parameters.
    for parameter_name in ["query", "q", "destination"]:
        parameter_values = query_parameters.get(
            parameter_name,
            []
        )

        if not parameter_values:
            continue

        possible_name = clean_google_place_name(
            parameter_values[0]
        )

        if not possible_name:
            continue

        # Do not use a coordinate pair as the location name.
        coordinate_only = re.fullmatch(
            r"\s*-?\d+(?:\.\d+)?\s*,\s*"
            r"-?\d+(?:\.\d+)?\s*",
            possible_name
        )

        if not coordinate_only:
            return possible_name

    return None


def extract_coordinates_from_google_url(url):
    """
    Extract latitude and longitude from common Google Maps URL
    patterns.
    """
    decoded_url = unquote(url)
    parsed_url = urlparse(decoded_url)
    query_parameters = parse_qs(parsed_url.query)

    coordinate_patterns = [
        # Standard Maps URL:
        # /@38.881600,-77.091000,17z
        r"@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)",

        # Google Maps data block:
        # !3d38.881600!4d-77.091000
        r"!3d(-?\d+(?:\.\d+)?).*?!4d(-?\d+(?:\.\d+)?)",

        # Alternate data block:
        # !2d-77.091000!3d38.881600
        # This pattern is longitude first, latitude second.
        r"!2d(-?\d+(?:\.\d+)?).*?!3d(-?\d+(?:\.\d+)?)",
    ]

    # Standard @latitude,longitude pattern.
    standard_match = re.search(
        coordinate_patterns[0],
        decoded_url
    )

    if standard_match:
        latitude = float(standard_match.group(1))
        longitude = float(standard_match.group(2))
        return latitude, longitude

    # !3d latitude and !4d longitude.
    data_match = re.search(
        coordinate_patterns[1],
        decoded_url
    )

    if data_match:
        latitude = float(data_match.group(1))
        longitude = float(data_match.group(2))
        return latitude, longitude

    # !2d longitude and !3d latitude.
    alternate_data_match = re.search(
        coordinate_patterns[2],
        decoded_url
    )

    if alternate_data_match:
        longitude = float(alternate_data_match.group(1))
        latitude = float(alternate_data_match.group(2))
        return latitude, longitude

    # Query parameters such as:
    # ?query=38.881600,-77.091000
    # ?q=38.881600,-77.091000
    for parameter_name in [
        "query",
        "q",
        "destination",
        "ll"
    ]:
        parameter_values = query_parameters.get(
            parameter_name,
            []
        )

        for parameter_value in parameter_values:
            coordinate_match = re.search(
                r"(-?\d+(?:\.\d+)?)\s*,\s*"
                r"(-?\d+(?:\.\d+)?)",
                parameter_value
            )

            if coordinate_match:
                latitude = float(
                    coordinate_match.group(1)
                )
                longitude = float(
                    coordinate_match.group(2)
                )
                return latitude, longitude

    raise ValueError(
        "Coordinates were not found in this Google Maps URL. "
        "Open the exact place or dropped pin in Google Maps, "
        "select Share, and copy that link."
    )


def parse_google_maps_url(url):
    """
    Resolve a Google Maps URL and return its name and coordinates.
    """
    resolved_url = resolve_google_maps_url(url)

    place_name = extract_name_from_google_url(
        resolved_url
    )

    latitude, longitude = (
        extract_coordinates_from_google_url(
            resolved_url
        )
    )

    if not -90 <= latitude <= 90:
        raise ValueError(
            "The latitude extracted from the URL is invalid."
        )

    if not -180 <= longitude <= 180:
        raise ValueError(
            "The longitude extracted from the URL is invalid."
        )

    return {
        "name": place_name,
        "latitude": latitude,
        "longitude": longitude,
        "resolved_url": resolved_url,
    }

# ---------------------------------------------------------
# ADD-LOCATION FORM
# ---------------------------------------------------------

with st.expander(
    "Add a new location",
    expanded=False
):

    st.caption(
        "Open a place or dropped pin in Google Maps, select "
        "Share, and paste the copied link below."
    )

    with st.form(
        key="add_location_form",
        clear_on_submit=True
    ):

        google_maps_url = st.text_input(
            "Google Maps URL",
            placeholder=(
                "https://maps.app.goo.gl/..."
            )
        )

        place_type = st.text_input(
            "Location type",
            placeholder="Example: Coffee shop"
        )

        region = st.text_input(
            "Region",
            placeholder="Example: Arlington, VA"
        )

        submitted = st.form_submit_button(
            "Add location",
            type="primary"
        )

    if submitted:

        clean_url = google_maps_url.strip()
        clean_type = place_type.strip()
        clean_region = region.strip()

        if not clean_url:
            st.error("Enter a Google Maps URL.")

        else:
            try:
                parsed_location = parse_google_maps_url(
                    clean_url
                )

                clean_name = parsed_location["name"]
                latitude = parsed_location["latitude"]
                longitude = parsed_location["longitude"]

                if not clean_name:
                    clean_name = (
                        f"Google Maps location "
                        f"({latitude:.5f}, {longitude:.5f})"
                    )

                new_type = (
                    clean_type
                    if clean_type
                    else "User-added location"
                )

                new_region = (
                    clean_region
                    if clean_region
                    else "User added"
                )

                # Combine original and user-added locations
                # so duplicate checks cover both datasets.
                all_current_locations = pd.concat(
                    [
                        base_df,
                        st.session_state.user_locations
                    ],
                    ignore_index=True,
                    sort=False
                )

                all_current_locations["Latitude"] = (
                    pd.to_numeric(
                        all_current_locations["Latitude"],
                        errors="coerce"
                    )
                )

                all_current_locations["Longitude"] = (
                    pd.to_numeric(
                        all_current_locations["Longitude"],
                        errors="coerce"
                    )
                )

                # Treat matching coordinates as duplicates,
                # even if Google formats the name differently.
                duplicate = (
                    all_current_locations["Latitude"]
                    .round(5)
                    .eq(round(float(latitude), 5))
                    &
                    all_current_locations["Longitude"]
                    .round(5)
                    .eq(round(float(longitude), 5))
                ).any()

                if duplicate:
                    st.warning(
                        "A location with these coordinates "
                        "already exists."
                    )

                else:
                    new_location = pd.DataFrame(
                        [
                            {
                                "Location Name": clean_name,
                                "Brief Description": new_type,
                                "Region Hint": new_region,
                                "Latitude": float(latitude),
                                "Longitude": float(longitude),
                                "Coordinate Confidence / Basis": (
                                    "Extracted from Google Maps URL"
                                ),
                                "Added By User": True
                            }
                        ]
                    )

                    st.session_state.user_locations = pd.concat(
                        [
                            st.session_state.user_locations,
                            new_location
                        ],
                        ignore_index=True
                    )

                    st.session_state.user_locations[
                        "Latitude"
                    ] = pd.to_numeric(
                        st.session_state.user_locations[
                            "Latitude"
                        ],
                        errors="coerce"
                    )

                    st.session_state.user_locations[
                        "Longitude"
                    ] = pd.to_numeric(
                        st.session_state.user_locations[
                            "Longitude"
                        ],
                        errors="coerce"
                    )

                    # Make sure the data folder exists before
                    # attempting to save the CSV.
                    DATA_FOLDER.mkdir(
                        parents=True,
                        exist_ok=True
                    )

                    st.session_state.user_locations.to_csv(
                        USER_LOCATIONS_FILE,
                        index=False
                    )

                    if (
                        "selected_location_types"
                        not in st.session_state
                    ):
                        st.session_state[
                            "selected_location_types"
                        ] = [new_type]

                    elif (
                        new_type
                        not in st.session_state[
                            "selected_location_types"
                        ]
                    ):
                        st.session_state[
                            "selected_location_types"
                        ].append(new_type)

                    st.session_state.show_user_added = True

                    st.session_state[
                        "new_location_latitude"
                    ] = float(latitude)

                    st.session_state[
                        "new_location_longitude"
                    ] = float(longitude)

                    st.session_state[
                        "location_added_message"
                    ] = (
                        f"{clean_name} was added to the map "
                        f"at {latitude:.6f}, "
                        f"{longitude:.6f}."
                    )

                    st.rerun()

            except ValueError as error:
                st.error(str(error))

            except Exception as error:
                st.error(
                    "The Google Maps URL could not be processed. "
                    "Open the exact place in Google Maps, select "
                    "Share, and copy the link again."
                )

                with st.expander("Technical details"):
                    st.code(str(error))
# ---------------------------------------------------------
# COMBINE ORIGINAL AND USER-ADDED DATA
# ---------------------------------------------------------

base_df = base_df.copy()
base_df["Added By User"] = False

user_df = st.session_state.user_locations.copy()
user_df["Added By User"] = True

df = pd.concat(
    [
        base_df,
        user_df
    ],
    ignore_index=True,
    sort=False
)

df["Latitude"] = pd.to_numeric(
    df["Latitude"],
    errors="coerce"
)

df["Longitude"] = pd.to_numeric(
    df["Longitude"],
    errors="coerce"
)

df = df.dropna(
    subset=["Latitude", "Longitude"]
).copy()

df["Added By User"] = (
    df["Added By User"]
    .fillna(False)
    .astype(bool)
)


# ---------------------------------------------------------
# SIDEBAR FILTERS
# ---------------------------------------------------------

st.sidebar.header("Map filters")

location_types = sorted(
    df["Brief Description"]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)

# Initialize the selected types on the first run
if "selected_location_types" not in st.session_state:
    st.session_state.selected_location_types = (
        location_types.copy()
    )

else:
    # Remove selections that are no longer available
    st.session_state.selected_location_types = [
        location_type
        for location_type
        in st.session_state.selected_location_types
        if location_type in location_types
    ]

selected_types = st.sidebar.multiselect(
    "Location type",
    options=location_types,
    key="selected_location_types"
)

show_original = st.sidebar.checkbox(
    "Show original locations",
    value=True,
    key="show_original"
)

show_user_added = st.sidebar.checkbox(
    "Show user-added locations",
    value=True,
    key="show_user_added"
)


# ---------------------------------------------------------
# APPLY FILTERS
# ---------------------------------------------------------

filtered = df[
    df["Brief Description"]
    .astype(str)
    .isin(selected_types)
].copy()

if show_original and not show_user_added:
    filtered = filtered[
        filtered["Added By User"] == False
    ].copy()

elif show_user_added and not show_original:
    filtered = filtered[
        filtered["Added By User"] == True
    ].copy()

elif not show_original and not show_user_added:
    filtered = filtered.iloc[0:0].copy()


# ----------------------------------------ELDS
# ---------------------------------------------------------

filtered["Location Source"] = filtered[
    "Added By User"
].map(
    {
        True: "User added",
        False: "Original dataset"
    }
)

# Convert fields to strings where needed so PyDeck can
# render them consistently.
filtered["Location Name"] = (
    filtered["Location Name"]
    .fillna("Unnamed location")
    .astype(str)
)

filtered["Brief Description"] = (
    filtered["Brief Description"]
    .fillna("Not specified")
    .astype(str)
)

filtered["Region Hint"] = (
    filtered["Region Hint"]
    .fillna("Not specified")
    .astype(str)
)


# ---------------------------------------------------------
# SPLIT DATA INTO SEPARATE MAP LAYERS
# ---------------------------------------------------------

original_locations = filtered[
    filtered["Added By User"] == False
].copy()

user_locations = filtered[
    filtered["Added By User"] == True
].copy()


# ---------------------------------------------------------
# MAP POSITION
# ---------------------------------------------------------

if (
    "new_location_latitude" in st.session_state
    and "new_location_longitude" in st.session_state
):
    # Center the map on the most recently added location
    map_latitude = st.session_state.new_location_latitude
    map_longitude = st.session_state.new_location_longitude
    map_zoom = 12

elif not filtered.empty:
    map_latitude = filtered["Latitude"].mean()
    map_longitude = filtered["Longitude"].mean()
    map_zoom = 3.5

else:
    map_latitude = 39.5
    map_longitude = -98.35
    map_zoom = 3.5


# ---------------------------------------------------------
# MAP LAYERS
# ---------------------------------------------------------

original_layer = pdk.Layer(
    "ScatterplotLayer",
    data=original_locations,
    get_position="[Longitude, Latitude]",
    get_fill_color=[193, 253, 59, 220],
    get_line_color=[255, 255, 255],
    get_radius=8,
    radius_min_pixels=5,
    radius_max_pixels=14,
    line_width_min_pixels=1,
    stroked=True,
    filled=True,
    pickable=True,
    auto_highlight=True,
    highlight_color=[255, 255, 255, 255]
)

user_layer = pdk.Layer(
    "ScatterplotLayer",
    data=user_locations,
    get_position="[Longitude, Latitude]",
    get_fill_color=[128, 221, 235, 200],
    get_line_color=[255, 255, 255],
    get_radius=8,
    radius_min_pixels=5,
    radius_max_pixels=14,
    line_width_min_pixels=1,
    stroked=True,
    filled=True,
    pickable=True,
    auto_highlight=True,
    highlight_color=[255, 255, 255, 255]
)


# ---------------------------------------------------------
# MAP VIEW
# ---------------------------------------------------------

view_state = pdk.ViewState(
    latitude=map_latitude,
    longitude=map_longitude,
    zoom=map_zoom,
    min_zoom=1,
    max_zoom=18,
    pitch=0,
    bearing=0
)


# ---------------------------------------------------------
# TOOLTIP
# ---------------------------------------------------------

tooltip = {
    "html": """
        <div style="font-family: Arial, sans-serif;">
            <div style="
                color: #C1FD3B;
                font-size: 16px;
                font-weight: 700;
                margin-bottom: 6px;
            ">
                {Location Name}
            </div>

            <b>Type:</b> {Brief Description}<br/>
            <b>Region:</b> {Region Hint}<br/>
            <b>Source:</b> {Location Source}<br/>
            <b>Latitude:</b> {Latitude}<br/>
            <b>Longitude:</b> {Longitude}
        </div>
    """,
    "style": {
        "backgroundColor": "#161B22",
        "color": "#FFFFFF",
        "fontSize": "13px",
        "border": "1px solid #C1FD3B",
        "borderRadius": "8px",
        "padding": "10px"
    }
}

# ---------------------------------------------------------
# DISPLAY MAP
# ---------------------------------------------------------

deck = pdk.Deck(
    layers=[
        original_layer,
        user_layer
    ],
    initial_view_state=view_state,
    tooltip=tooltip
)

st.pydeck_chart(
    deck,
    height=700
)


# ---------------------------------------------------------
# MAP SUMMARY
# ---------------------------------------------------------

visible_user_locations = int(
    filtered["Added By User"]
    .eq(True)
    .sum()
)

st.caption(
    f"Showing {len(filtered):,} of {len(df):,} locations. "
    f"User-added locations saved: "
    f"{len(st.session_state.user_locations):,}. "
    f"User-added locations currently visible: "
    f"{visible_user_locations:,}."
)


# ---------------------------------------------------------
# USER-ADDED LOCATION MANAGEMENT
# ---------------------------------------------------------

if not st.session_state.user_locations.empty:

    with st.expander("Manage user-added locations"):

        display_columns = [
            "Location Name",
            "Brief Description",
            "Region Hint",
            "Latitude",
            "Longitude"
        ]

        st.dataframe(
            st.session_state.user_locations[
                display_columns
            ],
            width="stretch",
            hide_index=True
        )

        downloadable_data = (
            st.session_state.user_locations
            .to_csv(index=False)
            .encode("utf-8")
        )

        st.download_button(
            label="Download user-added locations",
            data=downloadable_data,
            file_name="user_added_locations.csv",
            mime="text/csv"
        )

        st.write(
            "User-added location file:",
            USER_LOCATIONS_FILE
        )

        if st.button(
            "Delete all user-added locations",
            type="secondary"
        ):
            st.session_state.user_locations = pd.DataFrame(
                columns=USER_LOCATION_COLUMNS
            )

            if USER_LOCATIONS_FILE.exists():
                USER_LOCATIONS_FILE.unlink()

            # Clear the recently added point used for centering
            st.session_state.pop(
                "new_location_latitude",
                None
            )

            st.session_state.pop(
                "new_location_longitude",
                None
            )

            st.session_state.location_added_message = (
                "All user-added locations were deleted."
            )

            st.rerun()