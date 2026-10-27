import re
import time
from pathlib import Path
from urllib.parse import unquote

import pandas as pd

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ---------------------------------------------------------
# SETTINGS
# ---------------------------------------------------------

INPUT_FILE = Path(r"C:\Python\food_proj\data\food_loc.xlsx")
OUTPUT_FILE = Path(r"C:\Python\food_proj\data\food_loc_exact.xlsx")

WAIT_TIME = 15


# ---------------------------------------------------------
# EXTRACT COORDINATES FROM GOOGLE MAPS URL
# ---------------------------------------------------------

def extract_coordinates(url):
    url = unquote(url)

    # Prefer actual place coordinates
    pin = re.search(
        r"!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)",
        url
    )

    if pin:
        return (
            float(pin.group(1)),
            float(pin.group(2)),
            "Google Maps place pin"
        )

    # Fall back to map center
    center = re.search(
        r"@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)",
        url
    )

    if center:
        return (
            float(center.group(1)),
            float(center.group(2)),
            "Google Maps map center"
        )

    return None, None, "Coordinates not found"


# ---------------------------------------------------------
# SEARCH GOOGLE MAPS
# ---------------------------------------------------------

def search_google_maps(driver, wait, query):

    driver.get("https://www.google.com/maps")

    search_box = wait.until(
        EC.presence_of_element_located(
            (By.NAME, "q")
        )
    )

    search_box.clear()
    search_box.send_keys(query)
    search_box.send_keys(Keys.ENTER)

    # Wait until Google changes the URL
    wait.until(
        lambda d:
        "/maps/" in d.current_url
        and query.split()[0].lower()
        or "@" in d.current_url
    )

    # Give the place page a moment to fully resolve
    time.sleep(2)

    return driver.current_url


# ---------------------------------------------------------
# LOAD EXCEL
# ---------------------------------------------------------

df = pd.read_excel(INPUT_FILE)

# Preserve your existing coordinates
df["Old Latitude"] = df["Latitude"]
df["Old Longitude"] = df["Longitude"]

# Create new fields
df["Google Maps Place URL"] = None
df["Exact Latitude"] = None
df["Exact Longitude"] = None
df["Coordinate Source"] = None
df["Geocode Status"] = None


# ---------------------------------------------------------
# OPEN CHROME
# ---------------------------------------------------------

options = webdriver.ChromeOptions()

options.add_argument("--start-maximized")

driver = webdriver.Chrome(
    options=options
)

wait = WebDriverWait(
    driver,
    WAIT_TIME
)


# ---------------------------------------------------------
# PROCESS EVERY LOCATION
# ---------------------------------------------------------

try:

    for index, row in df.iterrows():

        name = str(row["Location Name"]).strip()

        region = str(
            row.get("Region Hint", "")
        ).strip()

        query = f"{name} {region}"

        print(
            f"[{index + 1}/{len(df)}] "
            f"Searching: {query}"
        )

        try:

            url = search_google_maps(
                driver,
                wait,
                query
            )

            lat, lon, source = extract_coordinates(
                url
            )

            df.loc[
                index,
                "Google Maps Place URL"
            ] = url

            df.loc[
                index,
                "Exact Latitude"
            ] = lat

            df.loc[
                index,
                "Exact Longitude"
            ] = lon

            df.loc[
                index,
                "Coordinate Source"
            ] = source

            if lat is not None:

                df.loc[
                    index,
                    "Geocode Status"
                ] = "Success"

                print(
                    f"    {lat}, {lon}"
                )

            else:

                df.loc[
                    index,
                    "Geocode Status"
                ] = "URL found; no coordinates"

                print(
                    "    Coordinates not found"
                )

        except Exception as e:

            df.loc[
                index,
                "Geocode Status"
            ] = f"Failed: {type(e).__name__}"

            print(
                f"    FAILED: {e}"
            )

        # Save continuously so you won't lose everything
        # if Chrome crashes halfway through.
        df.to_excel(
            OUTPUT_FILE,
            index=False
        )

        # Be gentle with Google Maps
        time.sleep(1)


finally:

    driver.quit()


# ---------------------------------------------------------
# FINALIZE
# ---------------------------------------------------------

success = df["Exact Latitude"].notna()

df.loc[
    success,
    "Latitude"
] = df.loc[
    success,
    "Exact Latitude"
]

df.loc[
    success,
    "Longitude"
] = df.loc[
    success,
    "Exact Longitude"
]

df.to_excel(
    OUTPUT_FILE,
    index=False
)

print()
print("Finished")
print(
    f"Coordinates found: "
    f"{success.sum()} / {len(df)}"
)
print(
    f"Saved to: {OUTPUT_FILE}"
)