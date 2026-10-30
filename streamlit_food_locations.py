from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import Request, urlopen
import re

import pandas as pd
import pydeck as pdk
import streamlit as st
from supabase import create_client



url = st.secrets["supabase"]["url"]
key = st.secrets["supabase"]["key"]

supabase = create_client(url, key)

response = (
    supabase
    .table("food_locations")
    .select("*")
    .execute()
)

print(response.data)


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

    [data-testid="stExpander"] summary:hover {
        background: var(--field) !important;
    }

    [data-testid="stExpander"] summary:hover p,
    [data-testid="stExpander"] summary:hover span,
    [data-testid="stExpander"] summary:hover svg {
        color: var(--accent) !important;
        fill: var(--accent) !important;
    }

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


# ---------------------------------------------------------
# SUCCESS MESSAGE
# ---------------------------------------------------------

if "location_added_message" in st.session_state:
    st.success(st.session_state.location_added_message)
    del st.session_state.location_added_message


# ---------------------------------------------------------
# FILE PATHS
# ---------------------------------------------------------

APP_FOLDER = Path(__file__).resolve().parent
DATA_FOLDER = APP_FOLDER / "data"

BASE_FILE = DATA_FOLDER / "food_loc_exact.xlsx"


# ---------------------------------------------------------
# REQUIRED COLUMNS
# ---------------------------------------------------------

USER_LOCATION_COLUMNS = [
    "Supabase ID",
    "Location Name",
    "Brief Description",
    "Region Hint",
    "Latitude",
    "Longitude",
    "Coordinate Confidence / Basis",
    "Added By User",
    "Google Maps URL"
]


# ---------------------------------------------------------
# SUPABASE CONNECTION
# ---------------------------------------------------------

@st.cache_resource
def get_supabase():
    """
    Create one reusable Supabase client.
    Credentials come from Streamlit Secrets.
    """

    supabase_url = st.secrets["supabase"]["url"]
    supabase_key = st.secrets["supabase"]["key"]

    return create_client(
        supabase_url,
        supabase_key
    )


def load_user_locations():
    """
    Load all permanently saved user locations from Supabase.
    """

    response = (
        get_supabase()
        .table("food_locations")
        .select("*")
        .order("id")
        .execute()
    )

    records = response.data or []

    if not records:
        return pd.DataFrame(
            columns=USER_LOCATION_COLUMNS
        )

    additions = pd.DataFrame(records)

    rename_columns = {
        "id": "Supabase ID",
        "location_name": "Location Name",
        "brief_description": "Brief Description",
        "region_hint": "Region Hint",
        "latitude": "Latitude",
        "longitude": "Longitude",
        "coordinate_basis": "Coordinate Confidence / Basis",
        "added_by_user": "Added By User",
        "google_maps_url": "Google Maps URL"
    }

    additions = additions.rename(
        columns=rename_columns
    )

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


def save_user_location(location):
    """
    Permanently save one location to Supabase.
    """

    database_row = {
        "location_name": location[
            "Location Name"
        ],
        "brief_description": location[
            "Brief Description"
        ],
        "region_hint": location[
            "Region Hint"
        ],
        "latitude": float(
            location["Latitude"]
        ),
        "longitude": float(
            location["Longitude"]
        ),
        "coordinate_basis": location[
            "Coordinate Confidence / Basis"
        ],
        "google_maps_url": location[
            "Google Maps URL"
        ],
        "added_by_user": True
    }

    (
        get_supabase()
        .table("food_locations")
        .insert(database_row)
        .execute()
    )


def delete_all_user_locations():
    """
    Delete all user-added locations from Supabase.

    Every row in this table is a user-added location,
    so the filter targets added_by_user = True.
    """

    (
        get_supabase()
        .table("food_locations")
        .delete()
        .eq("added_by_user", True)
        .execute()
    )

def delete_selected_user_locations(location_ids):
    """
    Permanently delete selected locations from Supabase
    using their unique database IDs.
    """

    if not location_ids:
        return

    (
        get_supabase()
        .table("food_locations")
        .delete()
        .in_("id", location_ids)
        .execute()
    )

def refresh_user_locations():
    """
    Reload the latest saved locations from Supabase.
    """

    st.session_state.user_locations = (
        load_user_locations()
    )


# ---------------------------------------------------------
# LOAD BASE DATA
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


base_df = load_base_locations()


# ---------------------------------------------------------
# LOAD SAVED SUPABASE LOCATIONS
# ---------------------------------------------------------

try:
    refresh_user_locations()

except Exception as error:

    st.error(
        "The app could not load saved locations from Supabase."
    )

    with st.expander("Supabase error details"):
        st.code(str(error))

    st.session_state.user_locations = pd.DataFrame(
        columns=USER_LOCATION_COLUMNS
    )


# ---------------------------------------------------------
# GOOGLE MAPS URL PARSING
# ---------------------------------------------------------

def resolve_google_maps_url(url):
    """
    Expand shortened Google Maps URLs such as maps.app.goo.gl.
    """

    clean_url = url.strip()

    if not clean_url:
        raise ValueError(
            "Enter a Google Maps URL."
        )

    parsed_url = urlparse(clean_url)

    if parsed_url.scheme not in {"http", "https"}:
        raise ValueError(
            "The Google Maps URL must begin with "
            "http:// or https://."
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
        hostname == host
        or hostname.endswith(f".{host}")
        for host in allowed_google_hosts
    )

    if not is_google_url:
        raise ValueError(
            "Enter a URL copied from Google Maps."
        )

    if hostname in {
        "maps.app.goo.gl",
        "goo.gl"
    }:

        request = Request(
            clean_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "AppleWebKit/537.36 "
                    "Chrome/120.0 "
                    "Safari/537.36"
                )
            }
        )

        try:
            with urlopen(
                request,
                timeout=10
            ) as response:

                return response.geturl()

        except Exception as error:
            raise ValueError(
                "The shortened Google Maps URL could "
                "not be expanded. In Google Maps, use "
                "Share > Copy link and try again."
            ) from error

    return clean_url


def clean_google_place_name(raw_name):

    if not raw_name:
        return None

    clean_name = unquote(raw_name)

    clean_name = clean_name.replace(
        "+",
        " "
    )

    clean_name = clean_name.replace(
        "_",
        " "
    )

    clean_name = re.sub(
        r"\s+",
        " ",
        clean_name
    ).strip()

    return clean_name or None


def extract_name_from_google_url(url):

    decoded_url = unquote(url)

    parsed_url = urlparse(
        decoded_url
    )

    query_parameters = parse_qs(
        parsed_url.query
    )

    place_match = re.search(
         r"/maps/(?:place|search)/([^/@]+)",
        decoded_url,
        flags=re.IGNORECASE
    )

    if place_match:

        possible_name = (
            clean_google_place_name(
                place_match.group(1)
            )
        )

        if possible_name:
            return possible_name

    for parameter_name in [
        "query",
        "q",
        "destination"
    ]:

        parameter_values = (
            query_parameters.get(
                parameter_name,
                []
            )
        )

        if not parameter_values:
            continue

        possible_name = (
            clean_google_place_name(
                parameter_values[0]
            )
        )

        if not possible_name:
            continue

        coordinate_only = re.fullmatch(
            r"\s*-?\d+(?:\.\d+)?\s*,\s*"
            r"-?\d+(?:\.\d+)?\s*",
            possible_name
        )

        if not coordinate_only:
            return possible_name

    return None


def extract_coordinates_from_google_url(url):

    decoded_url = unquote(url)

    parsed_url = urlparse(
        decoded_url
    )

    query_parameters = parse_qs(
        parsed_url.query
    )

    # Pattern 1:
    # @38.881600,-77.091000
    standard_match = re.search(
        r"@(-?\d+(?:\.\d+)?),"
        r"(-?\d+(?:\.\d+)?)",
        decoded_url
    )

    if standard_match:

        latitude = float(
            standard_match.group(1)
        )

        longitude = float(
            standard_match.group(2)
        )

        return latitude, longitude

    # Pattern 2:
    # !3d38.881600!4d-77.091000
    data_match = re.search(
        r"!3d(-?\d+(?:\.\d+)?).*?"
        r"!4d(-?\d+(?:\.\d+)?)",
        decoded_url
    )

    if data_match:

        latitude = float(
            data_match.group(1)
        )

        longitude = float(
            data_match.group(2)
        )

        return latitude, longitude

    # Pattern 3:
    # !2d-77.091000!3d38.881600
    alternate_match = re.search(
        r"!2d(-?\d+(?:\.\d+)?).*?"
        r"!3d(-?\d+(?:\.\d+)?)",
        decoded_url
    )

    if alternate_match:

        longitude = float(
            alternate_match.group(1)
        )

        latitude = float(
            alternate_match.group(2)
        )

        return latitude, longitude

    # Query parameters
    for parameter_name in [
        "query",
        "q",
        "destination",
        "ll"
    ]:

        parameter_values = (
            query_parameters.get(
                parameter_name,
                []
            )
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

    resolved_url = (
        resolve_google_maps_url(url)
    )

    place_name = (
        extract_name_from_google_url(
            resolved_url
        )
    )

    latitude, longitude = (
        extract_coordinates_from_google_url(
            resolved_url
        )
    )

    if not -90 <= latitude <= 90:
        raise ValueError(
            "The latitude extracted from the URL "
            "is invalid."
        )

    if not -180 <= longitude <= 180:
        raise ValueError(
            "The longitude extracted from the URL "
            "is invalid."
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
            placeholder="https://maps.app.goo.gl/..."
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
            st.error(
                "Enter a Google Maps URL."
            )

        else:

            try:

                parsed_location = (
                    parse_google_maps_url(
                        clean_url
                    )
                )

                clean_name = (
                    parsed_location["name"]
                )

                latitude = (
                    parsed_location["latitude"]
                )

                longitude = (
                    parsed_location["longitude"]
                )

                if not clean_name:

                    clean_name = (
                        "Google Maps location "
                        f"({latitude:.5f}, "
                        f"{longitude:.5f})"
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

                all_current_locations = pd.concat(
                    [
                        base_df,
                        st.session_state.user_locations
                    ],
                    ignore_index=True,
                    sort=False
                )

                all_current_locations[
                    "Latitude"
                ] = pd.to_numeric(
                    all_current_locations[
                        "Latitude"
                    ],
                    errors="coerce"
                )

                all_current_locations[
                    "Longitude"
                ] = pd.to_numeric(
                    all_current_locations[
                        "Longitude"
                    ],
                    errors="coerce"
                )

                duplicate = (
                    all_current_locations[
                        "Latitude"
                    ]
                    .round(5)
                    .eq(
                        round(
                            float(latitude),
                            5
                        )
                    )
                    &
                    all_current_locations[
                        "Longitude"
                    ]
                    .round(5)
                    .eq(
                        round(
                            float(longitude),
                            5
                        )
                    )
                ).any()

                if duplicate:

                    st.warning(
                        "A location with these "
                        "coordinates already exists."
                    )

                else:

                    new_location = {
                        "Location Name":
                            clean_name,

                        "Brief Description":
                            new_type,

                        "Region Hint":
                            new_region,

                        "Latitude":
                            float(latitude),

                        "Longitude":
                            float(longitude),

                        "Coordinate Confidence / Basis":
                            "Extracted from Google Maps URL",

                        "Added By User":
                            True,

                        "Google Maps URL":
                            parsed_location[
                                "resolved_url"
                            ]
                    }

                    # PERMANENTLY SAVE TO SUPABASE
                    save_user_location(
                        new_location
                    )

                    # Reload database immediately
                    refresh_user_locations()

                    # Keep new type selected
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

                    st.session_state[
                        "show_user_added"
                    ] = True

                    st.session_state[
                        "new_location_latitude"
                    ] = float(latitude)

                    st.session_state[
                        "new_location_longitude"
                    ] = float(longitude)

                    st.session_state[
                        "location_added_message"
                    ] = (
                        f"{clean_name} was permanently "
                        "saved and added to the map."
                    )

                    st.rerun()

            except ValueError as error:

                st.error(
                    str(error)
                )

            except Exception as error:

                st.error(
                    "The location could not be added."
                )

                with st.expander(
                    "Technical details"
                ):
                    st.code(str(error))


# ---------------------------------------------------------
# COMBINE ORIGINAL AND USER-ADDED DATA
# ---------------------------------------------------------

base_df = base_df.copy()
base_df["Added By User"] = False

user_df = (
    st.session_state.user_locations.copy()
)

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
    subset=[
        "Latitude",
        "Longitude"
    ]
).copy()

df["Added By User"] = (
    df["Added By User"]
    .fillna(False)
    .astype(bool)
)


# ---------------------------------------------------------
# SIDEBAR FILTERS
# ---------------------------------------------------------

st.sidebar.header(
    "Map filters"
)

location_types = sorted(
    df["Brief Description"]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)

if (
    "selected_location_types"
    not in st.session_state
):

    st.session_state[
        "selected_location_types"
    ] = location_types.copy()

else:

    # Keep valid existing selections
    current_selections = [
        location_type
        for location_type
        in st.session_state[
            "selected_location_types"
        ]
        if location_type in location_types
    ]

    # Automatically select newly available types
    for location_type in location_types:
        if location_type not in current_selections:
            current_selections.append(
                location_type
            )

    st.session_state[
        "selected_location_types"
    ] = current_selections


selected_types = (
    st.sidebar.multiselect(
        "Location type",
        options=location_types,
        key="selected_location_types"
    )
)

show_original = (
    st.sidebar.checkbox(
        "Show original locations",
        value=True,
        key="show_original"
    )
)

show_user_added = (
    st.sidebar.checkbox(
        "Show user-added locations",
        value=True,
        key="show_user_added"
    )
)


# ---------------------------------------------------------
# APPLY FILTERS
# ---------------------------------------------------------

filtered = df[
    df["Brief Description"]
    .astype(str)
    .isin(selected_types)
].copy()

if (
    show_original
    and not show_user_added
):

    filtered = filtered[
        filtered["Added By User"] == False
    ].copy()

elif (
    show_user_added
    and not show_original
):

    filtered = filtered[
        filtered["Added By User"] == True
    ].copy()

elif (
    not show_original
    and not show_user_added
):

    filtered = (
        filtered.iloc[0:0].copy()
    )


# ---------------------------------------------------------
# DISPLAY FIELDS
# ---------------------------------------------------------

filtered["Location Source"] = (
    filtered["Added By User"]
    .map(
        {
            True: "User added",
            False: "Original dataset"
        }
    )
)

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
# MAP LAYERS
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
    "new_location_latitude"
    in st.session_state
    and
    "new_location_longitude"
    in st.session_state
):

    map_latitude = (
        st.session_state[
            "new_location_latitude"
        ]
    )

    map_longitude = (
        st.session_state[
            "new_location_longitude"
        ]
    )

    map_zoom = 12

elif not filtered.empty:

    map_latitude = (
        filtered["Latitude"].mean()
    )

    map_longitude = (
        filtered["Longitude"].mean()
    )

    map_zoom = 3.5

else:

    map_latitude = 39.5
    map_longitude = -98.35
    map_zoom = 3.5


# ---------------------------------------------------------
# PYDECK LAYERS
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
    highlight_color=[
        255,
        255,
        255,
        255
    ]
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
    highlight_color=[
        255,
        255,
        255,
        255
    ]
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
        "border":
            "1px solid #C1FD3B",
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
    f"Showing {len(filtered):,} "
    f"of {len(df):,} locations. "
    f"User-added locations saved: "
    f"{len(st.session_state.user_locations):,}. "
    f"User-added locations currently visible: "
    f"{visible_user_locations:,}."
)

# ---------------------------------------------------------
# USER-ADDED LOCATION MANAGEMENT
# ---------------------------------------------------------

if not st.session_state.user_locations.empty:

    with st.expander(
        "Manage user-added locations"
    ):

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

        # -------------------------------------------------
        # SELECTIVE DELETE
        # -------------------------------------------------

        st.markdown("### Delete selected locations")

        st.caption(
            "Select one or more locations to permanently "
            "remove from the map."
        )

        management_df = (
            st.session_state.user_locations.copy()
        )

        # Create unique, readable labels.
        management_df["Delete Label"] = (
            management_df["Location Name"]
            .fillna("Unnamed location")
            .astype(str)
            + " — "
            + management_df["Region Hint"]
            .fillna("Unknown region")
            .astype(str)
            + " ("
            + management_df["Latitude"]
            .round(5)
            .astype(str)
            + ", "
            + management_df["Longitude"]
            .round(5)
            .astype(str)
            + ")"
        )

        selected_for_deletion = st.multiselect(
            "Locations to delete",
            options=management_df[
                "Delete Label"
            ].tolist(),
            placeholder="Select locations...",
            key="locations_to_delete"
        )

        if selected_for_deletion:

            selected_rows = management_df[
                management_df[
                    "Delete Label"
                ].isin(selected_for_deletion)
            ].copy()

            st.caption(
                f"{len(selected_rows):,} "
                "location(s) selected."
            )

            confirm_selected_delete = st.checkbox(
                "I understand the selected locations "
                "will be permanently deleted.",
                key="confirm_selected_delete"
            )

            if st.button(
                "Delete selected locations",
                type="secondary",
                disabled=not confirm_selected_delete
            ):

                try:

                    location_ids = (
                        selected_rows[
                            "Supabase ID"
                        ]
                        .dropna()
                        .astype(int)
                        .tolist()
                    )

                    if not location_ids:
                        st.error(
                            "No valid Supabase IDs were found "
                            "for the selected locations."
                        )

                    else:

                        delete_selected_user_locations(
                            location_ids
                        )

                        # Reload the remaining locations
                        # directly from Supabase.
                        refresh_user_locations()

                        # Remove previous map-centering state,
                        # because that point may have been deleted.
                        st.session_state.pop(
                            "new_location_latitude",
                            None
                        )

                        st.session_state.pop(
                            "new_location_longitude",
                            None
                        )

                        # Clear selection state before rerunning.
                        st.session_state.pop(
                            "locations_to_delete",
                            None
                        )

                        st.session_state.pop(
                            "confirm_selected_delete",
                            None
                        )

                        st.session_state[
                            "location_added_message"
                        ] = (
                            f"{len(location_ids):,} "
                            "location(s) were deleted."
                        )

                        st.rerun()

                except Exception as error:

                    st.error(
                        "The selected locations could "
                        "not be deleted."
                    )

                    with st.expander(
                        "Technical details"
                    ):
                        st.code(str(error))

        st.divider()

        # -------------------------------------------------
        # DOWNLOAD
        # -------------------------------------------------

        downloadable_data = (
            st.session_state.user_locations
            .drop(
                columns=["Supabase ID"],
                errors="ignore"
            )
            .to_csv(index=False)
            .encode("utf-8")
        )

        st.download_button(
            label="Download user-added locations",
            data=downloadable_data,
            file_name="user_added_locations.csv",
            mime="text/csv"
        )

        st.caption(
            "User-added locations are stored "
            "permanently in Supabase."
        )

        st.divider()

        # -------------------------------------------------
        # DELETE ALL
        # -------------------------------------------------

        st.markdown("### Delete all locations")

        confirm_delete = st.checkbox(
            "I understand this will permanently "
            "delete all user-added locations.",
            key="confirm_delete_all"
        )

        if st.button(
            "Delete all user-added locations",
            type="secondary",
            disabled=not confirm_delete
        ):

            try:

                delete_all_user_locations()

                refresh_user_locations()

                st.session_state.pop(
                    "new_location_latitude",
                    None
                )

                st.session_state.pop(
                    "new_location_longitude",
                    None
                )

                st.session_state.location_added_message = (
                    "All user-added locations "
                    "were deleted."
                )

                st.rerun()

            except Exception as error:

                st.error(
                    "The saved locations could "
                    "not be deleted."
                )

                with st.expander(
                    "Technical details"
                ):
                    st.code(str(error))