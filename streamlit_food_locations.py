from pathlib import Path
import pandas as pd
import pydeck as pdk
import streamlit as st


# ---------------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------------

st.set_page_config(
    page_title="My Food Spots",
    layout="wide"
)

st.title("My Food Spots")


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

BASE_FILE = DATA_FOLDER / "food_loc.xlsx"
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

    if os.path.exists(USER_LOCATIONS_FILE):
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
# ADD-LOCATION FORM
# ---------------------------------------------------------

with st.expander(
    "Add a new location",
    expanded=False
):

    with st.form(
        key="add_location_form",
        clear_on_submit=True
    ):

        place_name = st.text_input(
            "Place name",
            placeholder="Example: Amanda's Coffee Shop"
        )

        place_type = st.text_input(
            "Location type",
            placeholder="Example: Coffee shop"
        )

        region = st.text_input(
            "Region",
            placeholder="Example: Arlington, VA"
        )

        coordinate_columns = st.columns(2)

        with coordinate_columns[0]:
            latitude = st.number_input(
                "Latitude",
                min_value=-90.0,
                max_value=90.0,
                value=None,
                step=0.000001,
                format="%.6f",
                placeholder="38.881600"
            )

        with coordinate_columns[1]:
            longitude = st.number_input(
                "Longitude",
                min_value=-180.0,
                max_value=180.0,
                value=None,
                step=0.000001,
                format="%.6f",
                placeholder="-77.091000"
            )

        submitted = st.form_submit_button(
            "Add location",
            type="primary"
        )

    if submitted:

        clean_name = place_name.strip()
        clean_type = place_type.strip()
        clean_region = region.strip()

        if not clean_name:
            st.error("Enter a place name.")

        elif latitude is None or longitude is None:
            st.error(
                "Enter both latitude and longitude."
            )

        else:
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

            # Combine the original and user-added locations
            # so duplicates can be checked against both.
            all_current_locations = pd.concat(
                [
                    base_df,
                    st.session_state.user_locations
                ],
                ignore_index=True,
                sort=False
            )

            all_current_locations["Latitude"] = pd.to_numeric(
                all_current_locations["Latitude"],
                errors="coerce"
            )

            all_current_locations["Longitude"] = pd.to_numeric(
                all_current_locations["Longitude"],
                errors="coerce"
            )

            duplicate = (
                all_current_locations["Location Name"]
                .fillna("")
                .astype(str)
                .str.strip()
                .str.casefold()
                .eq(clean_name.casefold())
                &
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
                    "A location with the same name and "
                    "coordinates already exists."
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
                                "Coordinates entered by user"
                            ),
                            "Added By User": True
                        }
                    ]
                )

                # Add the new row to session state
                st.session_state.user_locations = pd.concat(
                    [
                        st.session_state.user_locations,
                        new_location
                    ],
                    ignore_index=True
                )

                # Ensure proper coordinate types
                st.session_state.user_locations["Latitude"] = (
                    pd.to_numeric(
                        st.session_state.user_locations["Latitude"],
                        errors="coerce"
                    )
                )

                st.session_state.user_locations["Longitude"] = (
                    pd.to_numeric(
                        st.session_state.user_locations["Longitude"],
                        errors="coerce"
                    )
                )

                # Save user-added locations.
                # This automatically creates the CSV if it
                # does not already exist.
                st.session_state.user_locations.to_csv(
                    USER_LOCATIONS_FILE,
                    index=False
                )

                # Make sure the new location type remains selected
                # after the application reruns.
                if "selected_location_types" not in st.session_state:
                    st.session_state.selected_location_types = [
                        new_type
                    ]

                elif (
                    new_type
                    not in st.session_state.selected_location_types
                ):
                    st.session_state.selected_location_types.append(
                        new_type
                    )

                # Make sure user-added locations are visible
                st.session_state.show_user_added = True

                # Save the new coordinates so the map can zoom
                # to the newly added location after rerunning.
                st.session_state.new_location_latitude = float(
                    latitude
                )

                st.session_state.new_location_longitude = float(
                    longitude
                )

                st.session_state.location_added_message = (
                    f"{clean_name} was added to the map."
                )

                st.rerun()


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
    get_fill_color=[228, 87, 86, 200],
    get_line_color=[255, 255, 255],
    get_radius=8,
    radius_min_pixels=5,
    radius_max_pixels=14,
    line_width_min_pixels=1,
    stroked=True,
    filled=True,
    pickable=True,
    auto_highlight=True,
    highlight_color=[255, 200, 0, 255]
)

user_layer = pdk.Layer(
    "ScatterplotLayer",
    data=user_locations,
    get_position="[Longitude, Latitude]",
    get_fill_color=[0, 150, 136, 230],
    get_line_color=[255, 255, 255],
    get_radius=12,
    radius_min_pixels=8,
    radius_max_pixels=18,
    line_width_min_pixels=2,
    stroked=True,
    filled=True,
    pickable=True,
    auto_highlight=True,
    highlight_color=[255, 200, 0, 255]
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
        <b>{Location Name}</b><br/>
        <b>Type:</b> {Brief Description}<br/>
        <b>Region:</b> {Region Hint}<br/>
        <b>Source:</b> {Location Source}<br/>
        <b>Latitude:</b> {Latitude}<br/>
        <b>Longitude:</b> {Longitude}
    """,
    "style": {
        "backgroundColor": "#222222",
        "color": "white",
        "fontSize": "14px"
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

            if os.path.exists(USER_LOCATIONS_FILE):
                os.remove(USER_LOCATIONS_FILE)

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