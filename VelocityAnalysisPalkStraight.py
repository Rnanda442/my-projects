#!/usr/bin/env python
# coding: utf-8

# In[1]:


pip install obspy


# In[ ]:





# In[9]:


from obspy.clients.fdsn import Client
from obspy import UTCDateTime
import pandas as pd

# Time range: last 50 years
end_time = UTCDateTime.now()
start_time = end_time - 100 * 365 * 24 * 60 * 60

# Bounding box around Pondicherry/Tamil Nadu
minlatitude = 11.0
maxlatitude = 13.0
minlongitude = 78.5
maxlongitude = 81.0

# Define clients
clients = {
    "IRIS": Client("IRIS"),
    "USGS": Client("USGS")
}

# Function to extract earthquake info from a catalog
def extract_events(catalog, source_name):
    records = []
    for event in catalog:
        origin = event.preferred_origin() or event.origins[0]
        magnitude = event.preferred_magnitude() or event.magnitudes[0]
        records.append({
            "Source": source_name,
            "Time": origin.time.datetime,
            "Latitude": origin.latitude,
            "Longitude": origin.longitude,
            "Depth_km": origin.depth / 1000,
            "Magnitude": magnitude.mag,
            "Event_ID": event.resource_id.id.split("/")[-1]
        })
    return records

# Fetch from both sources and merge
all_events = []

for name, client in clients.items():
    try:
        print(f"🔍 Querying {name}...")
        catalog = client.get_events(starttime=start_time,
                                    endtime=end_time,
                                    minlatitude=minlatitude,
                                    maxlatitude=maxlatitude,
                                    minlongitude=minlongitude,
                                    maxlongitude=maxlongitude,
                                    minmagnitude=1.0,
                                    orderby="time")
        events = extract_events(catalog, name)
        print(f"✅ {len(events)} events retrieved from {name}")
        all_events.extend(events)
    except Exception as e:
        print(f"❌ Failed to retrieve from {name}: {e}")

# Convert to DataFrame and drop duplicates by Time + Lat + Lon + Magnitude
df = pd.DataFrame(all_events)
df = df.drop_duplicates(subset=["Time", "Latitude", "Longitude", "Magnitude"])

# Save to CSV

print("\n=== Earthquake Statistics Summary ===\n")

print(f"📌 Total earthquakes (deduplicated): {len(df)}")
print(f"🕒 Time range: {df['Time'].min()} to {df['Time'].max()}")
print(f"🌍 Latitude range: {df['Latitude'].min()} to {df['Latitude'].max()}")
print(f"🌍 Longitude range: {df['Longitude'].min()} to {df['Longitude'].max()}")

print("\n📏 Depth (km):")
print(f"   Min: {df['Depth_km'].min():.2f}")
print(f"   Max: {df['Depth_km'].max():.2f}")
print(f"   Mean: {df['Depth_km'].mean():.2f}")

print("\n🌋 Magnitude:")
print(f"   Min: {df['Magnitude'].min():.2f}")
print(f"   Max: {df['Magnitude'].max():.2f}")
print(f"   Mean: {df['Magnitude'].mean():.2f}")

print("\n📊 Magnitude distribution:")
magnitude_bins = pd.cut(df['Magnitude'], bins=[1, 2, 3, 4, 5, 6, 7, 10])
print(df.groupby(magnitude_bins).size())

df.to_csv("pondicherry_combined_earthquakes.csv", index=False)
print("\n📝 Saved to pondicherry_combined_earthquakes.csv")
print(df.head())


# 
# 
# This cell collects earthquake data for the Pondicherry and Tamil Nadu region using the ObsPy FDSN client. It first sets up the time window, looking back 100 years from the current date, and defines a bounding box around Pondicherry to limit the spatial extent of the query. Two data providers are used, IRIS and USGS, and both are queried for all earthquakes with a minimum magnitude of 1.0.
# 
# To make the results easier to work with, a helper function is defined to extract the most important information from each event in the catalog. For every earthquake, it records the source (IRIS or USGS), the event time, location (latitude and longitude), depth in kilometers, magnitude, and a unique event ID.
# 
# The script then loops through both clients, downloads the events, and adds them to a single list. If any query fails, the error is printed but the process continues with the other source. Once all available events are collected, they are converted into a pandas DataFrame, and duplicates are removed so that the same earthquake reported by both catalogs only appears once.
# 
# With the cleaned dataset, the code prints a summary of earthquake activity in the region. It shows the total number of earthquakes, the time span of the data, and the ranges of latitude and longitude covered. It also computes basic depth and magnitude statistics, including the minimum, maximum, and average values, and displays a simple distribution of earthquake magnitudes grouped into bins.
# 
# Finally, the full dataset is saved to a CSV file called `pondicherry_combined_earthquakes.csv`, and the first few rows are displayed as a preview of the output.
# 
# 

# In[7]:


pip install geopandas contextily


# In[10]:


import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import contextily as ctx
from shapely.geometry import Point

# Load CSV
df = pd.read_csv("pondicherry_combined_earthquakes.csv")

# Convert to GeoDataFrame
gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["Longitude"], df["Latitude"]))
gdf.set_crs(epsg=4326, inplace=True)  # WGS84
gdf = gdf.to_crs(epsg=3857)           # Web Mercator for tile overlay

# Bounding box for rectangle (same box converted to Web Mercator)
from shapely.geometry import box
bbox = gpd.GeoDataFrame(geometry=[box(*gdf.total_bounds)], crs=gdf.crs)

# Plot
fig, ax = plt.subplots(figsize=(10, 10))
gdf.plot(ax=ax, column="Magnitude", cmap="viridis", markersize=50, legend=True, edgecolor='black')
bbox.boundary.plot(ax=ax, color="red", linestyle="--", linewidth=2)

# Add satellite basemap
ctx.add_basemap(ax, source=ctx.providers.Esri.WorldImagery)

# Final touches
ax.set_title("🌍 Earthquakes in Pondicherry Region (Satellite View)")
ax.set_axis_off()
plt.tight_layout()
plt.show()


# In[12]:


from obspy.clients.fdsn import Client
from obspy import UTCDateTime
import pandas as pd

# Load IRIS-only events
df = pd.read_csv("pondicherry_combined_earthquakes.csv")
df = df[df["Source"] == "IRIS"]

# Initialize IRIS client
client = Client("IRIS")

# Settings
time_buffer = 12 * 60 * 60  # 12 hours in seconds
search_radius = 5.0  # degrees

# Collect station info
results = []

for idx, row in df.iterrows():
    try:
        event_time = UTCDateTime(row["Time"])
        lat, lon, depth = row["Latitude"], row["Longitude"], row["Depth_km"]

        print(f"\n🔍 Checking event at {event_time} (Lat: {lat}, Lon: {lon})")

        # Query nearby stations active around the event time
        inventory = client.get_stations(
            latitude=lat,
            longitude=lon,
            maxradius=search_radius,
            starttime=event_time - time_buffer,
            endtime=event_time + time_buffer,
            level="channel"
        )

        for network in inventory:
            for station in network:
                for channel in station:
                    results.append({
                        "Event_Time": event_time.datetime,
                        "Latitude": lat,
                        "Longitude": lon,
                        "Depth_km": depth,
                        "Network": network.code,
                        "Station": station.code,
                        "Channel": channel.code
                    })

        print(f"✅ Found {len(results)} channels for this event.")

    except Exception as e:
        print(f"⚠️ Skipping event {row['Time']} due to error: {e}")
        continue

# Save results
if results:
    out_df = pd.DataFrame(results)
    out_df.to_csv("iris_event_station_channels.csv", index=False)
    print("\n✅ Done! Saved station/channel info to: iris_event_station_channels.csv")
else:
    print("\n❌ No station data found for any events.")


# This cell takes the earthquake dataset created earlier and focuses only on the events retrieved from IRIS. After filtering the CSV file, it sets up a new IRIS client to query for nearby seismic stations that were active at the time of each earthquake. To do this, the script defines a search radius of five degrees around each event and allows a twelve-hour time buffer before and after the event time.
# 
# For each earthquake in the IRIS subset, the script queries the IRIS station service to find networks, stations, and channels that were operating in that space and time window. The information it collects includes the event time and location, along with the network code, station code, and channel code of the available instruments. This allows you to link earthquakes directly to the seismic stations that recorded them.
# 
# All of these results are stored in a list and then converted into a DataFrame. If any stations are found, the script saves them to a file called `iris_event_station_channels.csv`, which provides a structured record of which stations were active for each earthquake. If no stations are found for any events, it simply reports that outcome instead. This ensures that each earthquake can be traced to its potential station recordings, forming the basis for later waveform analysis.
# 

# In[14]:


import pandas as pd

# Load the full file
df = pd.read_csv("iris_event_station_channels.csv")

# Group by network and station, then collect unique channels
summary = df.groupby(["Network", "Station"])["Channel"].unique().reset_index()

# Convert channel list to comma-separated string
summary["Channels"] = summary["Channel"].apply(lambda x: ", ".join(sorted(set(x))))
summary.drop(columns=["Channel"], inplace=True)

# Save the station summary
summary.to_csv("station_channel_summary.csv", index=False)
pd.set_option('display.max_colwidth', None)
# Display result
summary.head(10)


# This cell takes the file of event–station–channel matches produced in the previous step and condenses it into a cleaner station summary. It begins by loading the CSV file of all recorded channels linked to each earthquake. Instead of keeping every row per event, it groups the data by network and station so that each station only appears once.
# 
# For each station, the script collects the unique set of channels that were recorded. These channel codes are then combined into a single comma-separated string, making it easier to see at a glance which instruments are available at each site. After dropping the intermediate column, the result is a streamlined table showing the network, station code, and the full list of channels.
# 
# Finally, this summary is saved as a new CSV file called `station_channel_summary.csv`. To make the output more readable inside the notebook, the maximum column width for display is increased, and the first ten rows of the summary table are shown. This provides a quick overview of station coverage without repeating information for every event.
# 

# In[16]:


from obspy.clients.fdsn import Client
from obspy import UTCDateTime
import pandas as pd

# Load the station list
df = pd.read_csv("iris_event_station_channels.csv")

# Use only the first 50 entries (optional to limit request size)
subset = df.drop_duplicates(subset=["Network", "Station"])  # Unique stations only

client = Client("IRIS")
inventory = None

for _, row in subset.iterrows():
    try:
        net = row["Network"]
        sta = row["Station"]
        t = UTCDateTime(row["Event_Time"])
        inv = client.get_stations(network=net, station=sta,
                                  starttime=t - 3600, endtime=t + 3600,
                                  level="response")

        if inventory is None:
            inventory = inv
        else:
            inventory += inv
        print(f"✅ Added: {net}.{sta}")
    except Exception as e:
        print(f"⚠️ Skipped: {net}.{sta} – {e}")
        continue

if inventory:
    inventory.write("pondicherry_stations.xml", format="STATIONXML")
    print("📦 Saved: pondicherry_stations.xml")
else:
    print("❌ No inventory data to write.")


# This cell retrieves detailed metadata for the seismic stations identified earlier. It loads the list of stations from the event–station file, reduces it to unique station entries, and then queries the IRIS client for each one. The request is made for a short time window around the event and includes the full instrument response information. All station inventories are combined together into a single object. If successful, the script saves the complete metadata to a StationXML file called `pondicherry_stations.xml`; otherwise, it reports that no data were available.
# 

# In[17]:


import pandas as pd
import os

# List of relevant files
files = [
    "pondicherry_combined_earthquakes.csv",
    "iris_event_station_channels.csv",
    "vertical_channels_only.csv",
    "station_channel_summary.csv",
    "pondicherry_stations.xml",
    "README.txt"
]

for file in files:
    print("\n" + "="*80)
    print(f"📂 FILE: {file}")
    print("="*80)

    if not os.path.exists(file):
        print("❌ File not found.")
        continue

    if file.endswith(".csv"):
        df = pd.read_csv(file)

        print(f"\n🔢 Rows: {len(df)} | Columns: {len(df.columns)}")
        print(f"\n🧾 Column Headers:\n{df.columns.tolist()}")
        print("\n👀 Preview (first 5 rows):")
        display(df.head())

        print("\n📊 Descriptive Stats (numeric columns):")
        display(df.describe())

    elif file.endswith(".xml"):
        print("📦 StationXML file. Use ObsPy to inspect structure if needed.")
        print("🛠️  Tip: use `obspy.read_inventory('pondicherry_stations.xml')` to view contents.")

    elif file.endswith(".txt"):
        with open(file, "r") as f:
            content = f.read()
        print("📝 Text file content preview:\n")
        print(content)

    else:
        print("⚠️ Unsupported file type.")


# In[ ]:





# In[19]:


import pandas as pd
from obspy import read_inventory

# Load main dataframes
events = pd.read_csv("pondicherry_combined_earthquakes.csv")
stations = pd.read_csv("iris_event_station_channels.csv")
station_summary = pd.read_csv("station_channel_summary.csv")

# Load station XML and extract lat/lon
inventory = read_inventory("pondicherry_stations.xml")
station_coords = []

for network in inventory:
    for station in network:
        station_coords.append({
            "Network": network.code,
            "Station": station.code,
            "Station_Latitude": station.latitude,
            "Station_Longitude": station.longitude,
            "Station_Elevation": station.elevation
        })

station_coords_df = pd.DataFrame(station_coords)

# Merge events into station-channel rows
merged = pd.merge(stations,
                  events,
                  how="left",
                  left_on=["Event_Time", "Latitude", "Longitude", "Depth_km"],
                  right_on=["Time", "Latitude", "Longitude", "Depth_km"])

merged.drop(columns=["Time"], inplace=True)

# Merge in all station channels
merged = pd.merge(merged, station_summary, how="left", on=["Network", "Station"])

# Merge in station coordinates
merged = pd.merge(merged, station_coords_df, how="left", on=["Network", "Station"])

# Rename for clarity
merged.rename(columns={"Channels": "All_Station_Channels"}, inplace=True)

# Reorder columns
final_cols = [
    "Event_Time", "Event_ID", "Source", "Magnitude",
    "Latitude", "Longitude", "Depth_km",
    "Network", "Station", "Station_Latitude", "Station_Longitude", "Station_Elevation",
    "Channel", "All_Station_Channels"
]

master = merged[final_cols]

# Save master file
master.to_csv("master_earthquake_station_channel.csv", index=False)
print("✅ Master file with station coordinates saved as: master_earthquake_station_channel.csv")


# This cell brings together all the different pieces of information into a single master dataset. It first loads the earthquake events, the event–station–channel matches, and the summarized station channel list. It also reads the StationXML file with ObsPy to extract precise station metadata, including latitude, longitude, and elevation.
# 
# After collecting these coordinates, the script merges everything step by step. The station–channel records are linked to their corresponding earthquake events, then enriched with the full list of available channels per station, and finally combined with the geographic metadata from the StationXML. Column names are adjusted for clarity, and the final dataset is reorganized so that event details, station information, and channel data are presented in a clean, consistent order.
# 
# The completed dataset is saved as `master_earthquake_station_channel.csv`, which now serves as a comprehensive reference linking each earthquake to the stations that could have recorded it, along with their location, elevation, and instrument details.
# 

# In[20]:


# Load master file
master = pd.read_csv("master_earthquake_station_channel.csv")

# Define common vertical component suffixes (channel codes that end in 'Z')
vertical_suffixes = ['Z']

# Filter: only rows with vertical components (for P-wave detection)
p_wave_stations = master[master['Channel'].str.endswith(tuple(vertical_suffixes))]

# Optional: drop any rows missing station location (useful for SAC distance/azimuth)
p_wave_stations = p_wave_stations.dropna(subset=["Station_Latitude", "Station_Longitude"])

# Save as new filtered file
p_wave_stations.to_csv("p_wave_capable_stations.csv", index=False)

# Display result
print(f"✅ Found {len(p_wave_stations)} records with vertical channels suitable for P-wave picking.")
p_wave_stations.head()


# This cell filters the master dataset to focus only on seismic stations with vertical component channels, which are the most useful for detecting P-wave arrivals. It loads the full earthquake–station–channel file and then keeps only those rows where the channel code ends with “Z,” the standard suffix for vertical sensors. To ensure clean geometry for later distance and azimuth calculations, it also drops any rows that are missing station latitude or longitude.
# 
# The resulting subset is saved as `p_wave_capable_stations.csv`, creating a focused list of events and stations that are directly suitable for P-wave analysis. The script then prints the number of valid records found and previews the first few rows for quick inspection.
# 

# In[3]:


from obspy.clients.fdsn import Client
from obspy import UTCDateTime
import pandas as pd

client = Client("IRIS")
df = pd.read_csv("p_wave_capable_stations.csv")

confirmed = []

# Try only one test channel per row
for i, row in df.iterrows():
    try:
        net = row["Network"]
        sta = row["Station"]
        cha = row["Channel"]
        t = UTCDateTime(row["Event_Time"])
        start = t - 20
        end = t + 40

        # Test availability via actual waveform request (without saving yet)
        st = client.get_waveforms(network=net,
                                  station=sta,
                                  location="*",  # wildcard helps
                                  channel=cha,
                                  starttime=start,
                                  endtime=end,
                                  attach_response=False)
        
        # If successful, append to confirmed list
        confirmed.append(row)
        print(f"✅ Data available: {net}.{sta}.{cha} at {row['Event_Time']}")

    except Exception as e:
        print(f"❌ No data: {net}.{sta}.{cha} – {e}")

# Save valid combinations
if confirmed:
    confirmed_df = pd.DataFrame(confirmed)
    confirmed_df.to_csv("waveform_confirmed.csv", index=False)
    print("📦 Saved: waveform_confirmed.csv")
else:
    print("⚠ No valid waveforms found.")


# This cell tests whether waveform data are actually available for the vertical-component stations selected earlier. It loads the list of P-wave capable stations and then, for each event–station–channel row, attempts a short waveform request from IRIS. The request window is set from 20 seconds before to 40 seconds after the event time, which should be enough to capture the first arrivals.
# 
# If the request succeeds, that row is marked as confirmed and added to a list. If it fails, usually due to missing data or a gap in coverage, the script prints a warning but continues with the next station. After checking all rows, the confirmed list is written to a new file, `waveform_confirmed.csv`, which contains only the stations where data can actually be downloaded. This ensures that the next stage of processing, such as P-wave picking, will only target events with valid waveform records.
# 

# In[28]:


from obspy.clients.fdsn import Client
from obspy import UTCDateTime
import os

# IRIS client setup
client = Client("IRIS")

# Output directory
os.makedirs("waveforms", exist_ok=True)

# Event times and channels to try
events = [
    {"time": UTCDateTime("2012-03-27T04:49:27"), "label": "event_2012"},
    {"time": UTCDateTime("2011-08-12T06:06:29"), "label": "event_2011"}
]

station_info = {
    "network": "II",
    "station": "PALK",
    "channels": ["BHZ", "LHZ", "VHZ"],  # try these in order
    "location": "*"  # wildcard helps find more data
}

# Loop through events
for event in events:
    for ch in station_info["channels"]:
        try:
            t_start = event["time"] - 120
            t_end = event["time"] + 400

            print(f"📥 Downloading {station_info['station']}.{ch} at {event['time']}")

            st = client.get_waveforms(
                network=station_info["network"],
                station=station_info["station"],
                location=station_info["location"],
                channel=ch,
                starttime=t_start,
                endtime=t_end
            )

            # Save MiniSEED
            mseed_file = f"waveforms/{event['label']}_{ch}.mseed"
            st.write(mseed_file, format="MSEED")
            print(f"✅ Saved: {mseed_file}")

            # Optional: Save as SAC
            # sac_file = f"waveforms/{event['label']}_{ch}.sac"
            # st.write(sac_file, format="SAC")

            # Plot
            st.plot(title=f"{event['label']} - {ch}")

        except Exception as e:
            print(f"❌ No data: {station_info['station']}.{ch} at {event['time']} – {e}")


# This cell downloads actual waveform data for two selected earthquakes, one from 2012 and one from 2011, using the IRIS client. It focuses on the PALK station in the II network and attempts to retrieve three possible vertical channels—BHZ, LHZ, and VHZ—trying each in turn until data are found. For each event, the request window spans two minutes before and about six and a half minutes after the event origin time, ensuring the arrival and early coda are captured.
# 
# If the data are available, the trace is saved to the `waveforms` directory in MiniSEED format, with the option to also save as SAC if needed. Each trace is also plotted for quick inspection in the notebook. If no data exist for a given channel and event, the script reports this and continues. This workflow ensures that complete, usable waveform files are created for downstream analysis such as picking arrival times or running signal processing.
# 

# In[7]:


from obspy import read
import matplotlib.pyplot as plt
import glob

# Configuration
channels = ["BHZ", "LHZ"]       # Only these
location = "00"                 # Only 00 channels
events = ["2011", "2012"]
t_before = 60
t_after = 120

# Plot traces
for event in events:
    print(f"\n📊 Event: {event}\n" + "-"*40)
    files = sorted(glob.glob(f"waveforms/event_{event}_*.mseed"))
    for file in files:
        st = read(file)
        tr = st[0]

        # Skip unwanted location or channel
        if tr.stats.location != location or tr.stats.channel not in channels:
            continue

        # Trim
        tr.trim(tr.stats.starttime - t_before, tr.stats.starttime + t_after)

        # Plot
        plt.figure(figsize=(10, 3))
        plt.plot(tr.times(), tr.data, label=f"{event} - {tr.id}")
        plt.title(f"{event} - {tr.id}")
        plt.xlabel("Time (s)")
        plt.ylabel("Amplitude")
        plt.grid()
        plt.legend()
        plt.tight_layout()
        plt.show()


# This cell loads the MiniSEED files downloaded for the 2011 and 2012 earthquakes and plots them for inspection. It is configured to only use channels **BHZ** and **LHZ** with location code **00**, which helps filter out irrelevant traces. For each event, the script finds the corresponding waveform files, reads them with ObsPy, and selects the first trace.
# 
# Before plotting, each trace is trimmed to a shorter window: one minute before the file’s nominal start time and two minutes after. This keeps the plots focused on the part of the waveform near the arrival time. The trimmed trace is then plotted using Matplotlib, with time in seconds on the x-axis and amplitude on the y-axis. Each plot includes the event year and channel ID in the title and legend, making it easy to compare traces across events and channels. This provides a quick visual check that the right data were retrieved and that the vertical components are ready for further picking or processing.
# 

# In[8]:


import pandas as pd

# Store picks here
manual_picks = []

# Ask for P-arrival times
for event in events:
    files = sorted(glob.glob(f"waveforms/event_{event}_*.mseed"))
    for file in files:
        st = read(file)
        tr = st[0]

        # Only include 00 BHZ or LHZ
        if tr.stats.location != location or tr.stats.channel not in channels:
            continue

        trace_id = tr.id
        trace_name = file.split("/")[-1]
        print(f"\n⏱️ {trace_name} — Channel: {tr.stats.channel}, Location: {tr.stats.location}")

        try:
            offset = float(input("Enter P-wave arrival time in seconds from trace start: "))
            pick_time = tr.stats.starttime + offset
        except:
            print("⚠️ Skipped.")
            continue

        manual_picks.append({
            "Event": event,
            "Trace": trace_name,
            "Channel": tr.stats.channel,
            "Location": tr.stats.location,
            "Offset_Seconds": offset,
            "P_Arrival_Time": pick_time.isoformat()
        })

# Save to CSV
df = pd.DataFrame(manual_picks)
df.to_csv("waveforms/manual_p_wave_picks.csv", index=False)
print("✅ Picks saved to: waveforms/manual_p_wave_picks.csv")


# This cell is set up for manual picking of P-wave arrival times from the waveform files. For each earthquake event and each MiniSEED trace, it checks that the channel is either **BHZ** or **LHZ** with location code **00**. If so, it displays the trace’s file name and metadata, then prompts the user to type in the P-wave arrival time as an offset in seconds from the start of the trace.
# 
# When an offset is entered, the script converts it into an absolute arrival time by adding the offset to the trace’s start time. Each pick is stored in a list with details including the event, trace file, channel, location, the entered offset, and the resulting arrival time in ISO format. After all traces have been reviewed, the picks are written to a CSV file called `manual_p_wave_picks.csv` in the `waveforms` directory. This creates a clean, structured record of manually identified P-wave arrivals that can be used in later analyses.
# 

# In[10]:


import pandas as pd

# Load your picks
picks_df = pd.read_csv("waveforms/manual_p_wave_picks.csv")

# Event metadata (add more as needed)
earthquake_info = {
    "2011": {
        "Latitude": 11.196,
        "Longitude": 79.250,
        "Depth_km": 10.0,
        "Magnitude": 3.5,
        "Date": "2011-08-12",
        "UTC_Time": "06:06:29"
    },
    "2012": {
        "Latitude": 11.245,
        "Longitude": 78.581,
        "Depth_km": 11.2,
        "Magnitude": 3.6,
        "Date": "2012-03-27",
        "UTC_Time": "04:49:27"
    }
}

# Merge picks with event metadata
summary = []
for _, row in picks_df.iterrows():
    event_id = row["Event"]
    info = earthquake_info[str(event_id)]  # Cast to string

    summary.append({
        "Event": event_id,
        "EQ_Date": info["Date"],
        "EQ_Time_UTC": info["UTC_Time"],
        "Latitude": info["Latitude"],
        "Longitude": info["Longitude"],
        "Depth_km": info["Depth_km"],
        "Magnitude": info["Magnitude"],
        "Trace": row["Trace"],
        "P_Arrival_Time": row["P_Arrival_Time"],
        "Offset_Seconds": row["Offset_Seconds"],
        "Channel": row["Channel"],
        "Station_Location": row["Location"]
    })

summary_df = pd.DataFrame(summary)
summary_df.to_csv("waveforms/earthquake_summary_table.csv", index=False)

import IPython.display as disp
disp.display(summary_df)


# This cell combines the manually picked P-wave arrivals with basic earthquake metadata to create a clean summary table. It begins by loading the picks file that contains the arrival times recorded in the previous step. A dictionary is then defined with key information for each earthquake of interest, including latitude, longitude, depth, magnitude, date, and origin time.
# 
# For every pick in the file, the script looks up the corresponding event in this dictionary and merges the metadata with the pick details. The final table includes event information alongside the trace name, the manually entered arrival time, the offset in seconds, the channel, and the station location code.
# 
# Once all rows are assembled, the summary is saved to a CSV file called `earthquake_summary_table.csv` in the `waveforms` directory. It is also displayed directly in the notebook for quick review. This produces a comprehensive record that ties together the earthquake parameters with the arrival picks, ready for analysis or visualization.
# 

# In[11]:


from math import radians, sin, cos, sqrt, atan2

# PALK station location
station_lat = 9.153
station_lon = 79.875

# Add epicentral distance to each row
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0  # Radius of Earth in km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

summary_df["Epicentral_Distance_km"] = summary_df.apply(
    lambda row: haversine(row["Latitude"], row["Longitude"], station_lat, station_lon), axis=1
)

summary_df.to_csv("waveforms/earthquake_summary_with_distance.csv", index=False)
summary_df[["Event", "Trace", "Epicentral_Distance_km"]]


# This cell calculates the epicentral distance between each earthquake and the PALK seismic station. It defines the station’s latitude and longitude and then applies the haversine formula, which accounts for the curvature of the Earth, to compute the great-circle distance in kilometers. The distance calculation is applied row by row to the summary table of earthquake picks, and the results are stored in a new column called `Epicentral_Distance_km`.
# 
# The updated table is saved to a new file, `earthquake_summary_with_distance.csv`, ensuring the event information, arrival picks, and calculated distances are preserved together. Finally, the notebook displays a concise view of each event, its trace, and the corresponding epicentral distance, making it easier to reference distances directly when analyzing travel times or estimating seismic velocities.
# 

# In[12]:


# Add velocity column: V = D / T
summary_df["P_Wave_Velocity_kmps"] = summary_df["Epicentral_Distance_km"] / summary_df["Offset_Seconds"]

# Save updated table
summary_df.to_csv("waveforms/earthquake_summary_with_velocity.csv", index=False)

# Display key fields
summary_df[["Event", "Trace", "Epicentral_Distance_km", "Offset_Seconds", "P_Wave_Velocity_kmps"]]


# This cell estimates the apparent P-wave velocity for each event–station pair by dividing the epicentral distance by the manually picked travel time. A new column, `P_Wave_Velocity_kmps`, is added to the summary table to store these values in kilometers per second. The updated dataset is saved to a new file called `earthquake_summary_with_velocity.csv`. To provide a focused view, the notebook then displays only the essential fields: event, trace, distance, travel time offset, and the calculated velocity. This makes it easy to evaluate whether the derived velocities fall within expected seismic ranges.
# 

# In[13]:


import folium

# Map center: Pondicherry area
map_center = [11.2, 79.0]
m = folium.Map(location=map_center, zoom_start=7)

# Add station (PALK)
folium.Marker(
    location=[9.153, 79.875],
    popup="II.PALK Station",
    icon=folium.Icon(color="blue", icon="tower", prefix="fa")
).add_to(m)

# Add earthquakes from summary_df
for _, row in summary_df.iterrows():
    folium.Marker(
        location=[row["Latitude"], row["Longitude"]],
        popup=f"Event {row['Event']} ({row['Channel']})\nMag {row['Magnitude']}",
        icon=folium.Icon(color="red", icon="bolt", prefix="fa")
    ).add_to(m)

m


# This cell creates an interactive Folium map to visualize the earthquakes alongside the PALK seismic station. The map is centered on the Pondicherry region and set to a zoom level that covers both the event locations and the station. A blue marker is placed at the PALK station coordinates, while each earthquake from the summary table is plotted as a red marker at its latitude and longitude.
# 
# Each earthquake marker includes a popup showing the event ID, the channel used for the pick, and the magnitude. This makes it easy to visually inspect how the events are distributed relative to the seismic station, providing a spatial context for the arrival time and velocity analysis. The result is an interactive map that can be zoomed and panned directly in the notebook.
# 

# In[11]:


get_ipython().system('pip uninstall fitz -y')
get_ipython().system('pip install --upgrade pymupdf')


# In[13]:


# If missing:  pip install pymupdf pillow matplotlib
import fitz  # PyMuPDF
from pathlib import Path

# === Edit these paths
TN_PDF = r"C:\Users\gargi\Downloads\Map_Tamil_Nadu_Pondicherry_State_Geology_and_Mineral_Maps_Geological_Survey_of_India.pdf"
SL_PDF = r"C:\Users\gargi\Downloads\ESCAP-1989-MN-Atlas-mineral-resources-sri-lanka-v.5-map.pdf"

OUT_DIR = Path("overlays"); OUT_DIR.mkdir(parents=True, exist_ok=True)
TN_PNG = OUT_DIR / "tamilnadu_geology_raw.png"
SL_PNG = OUT_DIR / "srilanka_geology_raw.png"

def pdf_first_page_to_png(pdf_path, out_png, dpi=400):
    doc = fitz.open(pdf_path)
    if doc.page_count == 0:
        raise ValueError(f"No pages in {pdf_path}")
    page = doc[0]  # first page only
    mat = fitz.Matrix(dpi/72, dpi/72)  # scale to desired DPI
    pix = page.get_pixmap(matrix=mat, alpha=False)
    pix.save(str(out_png))
    doc.close()
    return out_png

tn_png_path = pdf_first_page_to_png(TN_PDF, TN_PNG, dpi=400)
sl_png_path = pdf_first_page_to_png(SL_PDF, SL_PNG, dpi=400)
tn_png_path, sl_png_path


# This cell converts the first pages of two geological survey PDFs into high-resolution PNG images for later use as overlays. It uses PyMuPDF to open each file, render the first page at 400 DPI, and save the result as a PNG. The Tamil Nadu geology map and the Sri Lanka mineral resources map are processed this way, with the outputs saved in an `overlays` directory under the filenames `tamilnadu_geology_raw.png` and `srilanka_geology_raw.png`. The function returns the saved paths so they can be verified or used in subsequent steps.
# 

# In[15]:


# If missing: pip install pillow numpy matplotlib
from PIL import Image, ImageChops
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt

# ---- input PNGs you already created from the PDFs ----
TN_PNG  = Path("overlays/tamilnadu_geology_raw.png")
SL_PNG  = Path("overlays/srilanka_geology_raw.png")

OUT = Path("overlays")
OUT.mkdir(exist_ok=True)

# ---------- helpers ----------
def autocrop_white(input_path, output_path, bg_threshold=245):
    """Trim the white collar/margins."""
    im = Image.open(input_path).convert("RGB")
    bg = Image.new("RGB", im.size, (255, 255, 255))
    diff = ImageChops.difference(im, bg).convert("L")
    # treat very-near-white as background when finding bbox
    bbox = diff.point(lambda x: 0 if x < (255 - bg_threshold) else x).getbbox()
    (im if bbox is None else im.crop(bbox)).save(output_path)
    return output_path

def make_white_transparent(input_path, output_path, thr=245):
    """Set near-white to transparent (keep everything else)."""
    im = Image.open(input_path).convert("RGBA")
    arr = np.array(im, dtype=np.uint8)
    r, g, b, a = arr[...,0], arr[...,1], arr[...,2], arr[...,3]
    mask = (r > thr) & (g > thr) & (b > thr)
    arr[mask, 3] = 0
    Image.fromarray(arr).save(output_path)
    return output_path

def clean_white_and_blue(input_path, output_path,
                         white_thr=245, blue_thr=180, sat_thr=40):
    """
    Remove near-white + pale-blue background (for the Sri Lanka sheet).
    blue_thr: 'lightness' of blue channel above which + low saturation → remove
    sat_thr : tolerance so we keep saturated blue geology lines.
    """
    im = Image.open(input_path).convert("RGBA")
    arr = np.array(im, dtype=np.uint8)

    R, G, B, A = arr[...,0], arr[...,1], arr[...,2], arr[...,3]

    # near-white
    white_mask = (R > white_thr) & (G > white_thr) & (B > white_thr)

    # pale-blue: blue dominant & light, with low saturation
    max_c = np.maximum.reduce([R, G, B])
    min_c = np.minimum.reduce([R, G, B])
    saturation = (max_c - min_c)
    blue_mask = (B > blue_thr) & (B >= R) & (B >= G) & (saturation < sat_thr)

    remove_mask = white_mask | blue_mask
    arr[remove_mask, 3] = 0

    Image.fromarray(arr).save(output_path)
    return output_path

# ---------- process ----------
# Trim both
TN_TRIM = OUT / "tamilnadu_geology_trim.png"
SL_TRIM = OUT / "srilanka_geology_trim.png"
autocrop_white(TN_PNG, TN_TRIM)
autocrop_white(SL_PNG, SL_TRIM)

# Tamil Nadu: ONLY white cleaned
TN_CLEAN = OUT / "tamilnadu_geology_clean.png"
make_white_transparent(TN_TRIM, TN_CLEAN, thr=246)

# Sri Lanka: white + pale-blue cleaned
SL_CLEAN = OUT / "srilanka_geology_clean_noblue.png"
clean_white_and_blue(SL_TRIM, SL_CLEAN, white_thr=246, blue_thr=182, sat_thr=42)

# ---------- quick preview ----------
fig, ax = plt.subplots(1, 2, figsize=(14, 8))
ax[0].imshow(plt.imread(TN_CLEAN)); ax[0].set_title("Tamil Nadu (white cleaned)"); ax[0].axis("off")
ax[1].imshow(plt.imread(SL_CLEAN)); ax[1].set_title("Sri Lanka (white + pale-blue removed)"); ax[1].axis("off")
plt.tight_layout(); plt.show()

print("Saved:")
print(" -", TN_CLEAN)
print(" -", SL_CLEAN)


# This cell prepares the geology map images you rendered from the PDFs so they can be used as clean, transparent overlays. It starts by loading the two PNGs and creates an output folder. The first helper, `autocrop_white`, trims away white page margins by comparing each image to a pure-white background and cropping to the tightest non-white bounding box. Next, two cleaning functions handle backgrounds. `make_white_transparent` targets the Tamil Nadu sheet, converting near-white pixels (above a chosen brightness threshold) to full transparency while preserving colored geology. `clean_white_and_blue` is tailored to the Sri Lanka sheet, which often has a pale blue paper tint: it removes both near-white pixels and lightly tinted low-saturation blues, while leaving saturated blue features intact by checking simple saturation (max-min of RGB) and requiring blue dominance only when saturation is small. After trimming both maps, the Tamil Nadu image is cleaned for white only, and the Sri Lanka image is cleaned for both white and pale blue using slightly conservative thresholds to avoid eroding geology lines. The script then displays a side-by-side preview so you can visually verify that the page collar and background tint are gone while map content remains, and prints the saved paths for downstream geo-referencing or overlay steps.
# 

# In[26]:


# === Browser-based GCP picker (single cell) ===
# - Pan/zoom (wheel/trackpad; drag to pan)
# - Click to add a point, then enter lat/lon
# - Undo / Clear / Reset
# - Save JSON downloads sl_gcps.json
#
# Change SL_IMG_PATH to your geology map image.

import base64, io, webbrowser
from pathlib import Path
from PIL import Image

# --- CONFIG ---
SL_IMG_PATH = Path("overlays/srilanka_geology_clean_noblue.png")  # << your map image
OUT_HTML    = Path("sl_gcp_picker.html")                          # output HTML file

# --- Read and embed the image as base64 (no server needed) ---
img = Image.open(SL_IMG_PATH).convert("RGBA")
buf = io.BytesIO(); img.save(buf, format="PNG")
img_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

# --- HTML/JS template (no external deps) ---
template = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Sri Lanka geological map — GCP picker</title>
<style>
  html, body { height: 100%; margin: 0; font-family: system-ui, sans-serif; }
  #topbar {
    position: fixed; top: 0; left: 0; right: 0; z-index: 10;
    background: #111; color: #fff; padding: 8px 10px; display: flex; gap: 10px; align-items: center;
  }
  #topbar button { padding: 6px 10px; border-radius: 8px; border: 0; cursor: pointer; }
  #wrap { position: absolute; inset: 44px 0 0 0; background: #f7f7f7; overflow: hidden; }
  #canvas { display: block; margin: 0; width: 100%; height: 100%; background: #e6eef7; touch-action: none; }
  .chip { background: #ffc107; border: 1px solid #222; border-radius: 8px; padding: 2px 8px; margin-left: 6px; }
  .hint { opacity: .8; font-size: 12px; margin-left: 8px; }
</style>
</head>
<body>
<div id="topbar">
  <strong>Sri Lanka geological map — tap/click to add a GCP</strong>
  <span class="hint">Wheel/trackpad to zoom, drag to pan. Touch drag works; pinch zoom varies by browser.</span>
  <button id="zoomIn">+</button>
  <button id="zoomOut">−</button>
  <button id="reset">Reset</button>
  <button id="undo">Undo</button>
  <button id="save">Save JSON</button>
  <button id="clear">Clear</button>
  <span id="status" class="chip">0 points</span>
</div>
<div id="wrap"><canvas id="canvas"></canvas></div>

<script>
const imgSrc = "data:image/png;base64,IMG_B64";
const image = new Image();
image.src = imgSrc;

const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');

let W = 0, H = 0;
let imgW = 0, imgH = 0;

// Pan/zoom state
let scale = 1.0;
let minScale = 0.2, maxScale = 12;
let tx = 0, ty = 0;
let dragging = false;
let lastX = 0, lastY = 0;

// Picked points: [{px, py, lat, lon}]
let points = [];
const statusEl = document.getElementById('status');
function setStatus() { statusEl.textContent = points.length + " points"; }

// Resize canvas to fill container
function resize() {
  const rect = canvas.parentElement.getBoundingClientRect();
  W = canvas.width = Math.floor(rect.width * (window.devicePixelRatio || 1));
  H = canvas.height = Math.floor(rect.height * (window.devicePixelRatio || 1));
  canvas.style.width = rect.width + "px";
  canvas.style.height = rect.height + "px";
  draw();
}
window.addEventListener('resize', resize);

// Fit image on screen
function fitToScreen() {
  if (!imgW || !imgH) return;
  const sx = W / imgW, sy = H / imgH;
  scale = Math.min(sx, sy) * 0.95;
  tx = (W - imgW * scale) / 2;
  ty = (H - imgH * scale) / 2;
}

// Convert screen coords to image pixel coords
function screenToImage(x, y) {
  const ix = (x - tx) / scale;
  const iy = (y - ty) / scale;
  return [ix, iy];
}

// Draw image + points
function draw() {
  ctx.save();
  ctx.clearRect(0, 0, W, H);
  ctx.imageSmoothingEnabled = false;
  ctx.translate(tx, ty);
  ctx.scale(scale, scale);
  ctx.drawImage(image, 0, 0);
  for (let i=0; i<points.length; i++) {
    const p = points[i];
    ctx.beginPath();
    ctx.arc(p.px, p.py, 6/Math.max(scale, 0.5), 0, Math.PI*2);
    ctx.fillStyle = 'rgba(255, 235, 59, 0.9)';
    ctx.strokeStyle = '#000';
    ctx.lineWidth = 2/Math.max(scale, 0.5);
    ctx.fill(); ctx.stroke();
  }
  ctx.restore();
}

// Mouse/touch pan
canvas.addEventListener('mousedown', (e) => { dragging = true; lastX = e.clientX; lastY = e.clientY; });
window.addEventListener('mouseup', () => dragging = false);
window.addEventListener('mousemove', (e) => {
  if (!dragging) return;
  const dx = (e.clientX - lastX) * (window.devicePixelRatio || 1);
  const dy = (e.clientY - lastY) * (window.devicePixelRatio || 1);
  lastX = e.clientX; lastY = e.clientY;
  tx += dx; ty += dy;
  draw();
});
canvas.addEventListener('touchstart', (e) => {
  if (e.touches.length === 1) { dragging = true; lastX = e.touches[0].clientX; lastY = e.touches[0].clientY; }
}, {passive: false});
canvas.addEventListener('touchmove', (e) => {
  if (dragging && e.touches.length === 1) {
    const dx = (e.touches[0].clientX - lastX) * (window.devicePixelRatio || 1);
    const dy = (e.touches[0].clientY - lastY) * (window.devicePixelRatio || 1);
    lastX = e.touches[0].clientX; lastY = e.touches[0].clientY;
    tx += dx; ty += dy;
    draw();
  }
}, {passive: false});
canvas.addEventListener('touchend', ()=> dragging=false);

// Wheel zoom
canvas.addEventListener('wheel', (e) => {
  e.preventDefault();
  const rect = canvas.getBoundingClientRect();
  const cx = (e.clientX - rect.left) * (window.devicePixelRatio || 1);
  const cy = (e.clientY - rect.top) * (window.devicePixelRatio || 1);
  const delta = Math.sign(e.deltaY) * -0.1;
  const newScale = Math.min(maxScale, Math.max(minScale, scale * (1 + delta)));
  // zoom about cursor
  const [ix, iy] = screenToImage(cx, cy);
  scale = newScale;
  tx = cx - ix * scale;
  ty = cy - iy * scale;
  draw();
}, {passive:false});

// Click to add point (then prompt for lat/lon)
canvas.addEventListener('click', (e) => {
  if (Math.abs(e.clientX - lastX) > 2 || Math.abs(e.clientY - lastY) > 2) { return; } // ignore if it was a drag
  const rect = canvas.getBoundingClientRect();
  const cx = (e.clientX - rect.left) * (window.devicePixelRatio || 1);
  const cy = (e.clientY - rect.top) * (window.devicePixelRatio || 1);
  const [ix, iy] = screenToImage(cx, cy);
  const latStr = prompt("Latitude (decimal degrees):");
  const lonStr = prompt("Longitude (decimal degrees):");
  if (latStr === null || lonStr === null) return;
  const lat = parseFloat(latStr), lon = parseFloat(lonStr);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return alert("Invalid lat/lon");
  points.push({px: ix, py: iy, lat: lat, lon: lon});
  setStatus(); draw();
});

// Buttons
document.getElementById('reset').onclick = () => { fitToScreen(); draw(); };
document.getElementById('undo').onclick  = () => { points.pop(); setStatus(); draw(); };
document.getElementById('clear').onclick = () => { points = []; setStatus(); draw(); };
document.getElementById('zoomIn').onclick = () => { scale = Math.min(maxScale, scale*1.2); draw(); };
document.getElementById('zoomOut').onclick = () => { scale = Math.max(minScale, scale/1.2); draw(); };

// Save JSON
document.getElementById('save').onclick = () => {
  const blob = new Blob([JSON.stringify(points, null, 2)], {type: "application/json"});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = "sl_gcps.json";
  a.click();
  URL.revokeObjectURL(a.href);
};

image.onload = () => {
  imgW = image.naturalWidth; imgH = image.naturalHeight;
  resize(); fitToScreen(); draw();
};
</script>
</body>
</html>
"""

# --- write file & open ---
html = template.replace("IMG_B64", img_b64)
OUT_HTML.write_text(html, encoding="utf-8")
print(f"Wrote {OUT_HTML.resolve()}")
try:
    webbrowser.open(OUT_HTML.resolve().as_uri())
except Exception:
    pass


# This cell builds a self-contained, browser-based ground-control-point (GCP) picker for your Sri Lanka geology overlay. It loads the cleaned PNG, embeds it directly into an HTML canvas as base64 (so no server is needed), and writes a single `sl_gcp_picker.html` file you can open locally. The minimal UI lets you pan and zoom, then click on the map to drop a point; each click prompts for latitude and longitude in decimal degrees. Points are stored as image-pixel coordinates paired with the entered geographic coordinates, which is exactly what you need for later geo-referencing or affine fitting. You can undo the last point, clear all points, reset the view, and adjust zoom with buttons or the mouse wheel; touch drag works on mobile for panning. When you’re done, the “Save JSON” button downloads the current set of GCPs as `sl_gcps.json`, preserving `[px, py, lat, lon]` for each pick. The script finishes by writing the HTML to disk and attempting to open it in your default browser, making this a single cell you can run in Jupyter to get an interactive GCP tool.
# 

# In[11]:


# === Browser-based GCP picker for "other map" (Tamil Nadu, etc.) ===
# Pan/zoom (wheel/trackpad; drag), click to add point → enter lat/lon,
# Undo / Clear / Reset, and Save JSON (downloads tn_gcps.json).
#
# 1) Set TN_IMG_PATH to your image (PNG/JPG).
# 2) Run cell — it creates tn_gcp_picker.html and opens it.

import base64, io, webbrowser
from pathlib import Path
from PIL import Image

# --- CONFIG ---
TN_IMG_PATH = Path("overlays/tamilnadu_geology_clean.png")  # <- change to your file
OUT_HTML    = Path("tn_gcp_picker.html")                    # output HTML filename
PAGE_TITLE  = "Tamil Nadu geological map — GCP picker"      # window title/text

# --- Read image & embed as base64 (no server needed) ---
img = Image.open(TN_IMG_PATH).convert("RGBA")
buf = io.BytesIO(); img.save(buf, format="PNG")
img_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

# --- HTML/JS template (no external deps) ---
template = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>PAGE_TITLE</title>
<style>
  html, body { height: 100%; margin: 0; font-family: system-ui, sans-serif; }
  #topbar {
    position: fixed; top: 0; left: 0; right: 0; z-index: 10;
    background: #111; color: #fff; padding: 8px 10px; display: flex; gap: 10px; align-items: center;
  }
  #topbar button { padding: 6px 10px; border-radius: 8px; border: 0; cursor: pointer; }
  #wrap { position: absolute; inset: 44px 0 0 0; background: #f7f7f7; overflow: hidden; }
  #canvas { display: block; width: 100%; height: 100%; background: #e6eef7; touch-action: none; }
  .chip { background: #ffc107; border: 1px solid #222; border-radius: 8px; padding: 2px 8px; margin-left: 6px; }
  .hint { opacity: .8; font-size: 12px; margin-left: 8px; }
</style>
</head>
<body>
<div id="topbar">
  <strong>PAGE_TITLE</strong>
  <span class="hint">Wheel/trackpad to zoom, drag to pan. Touch drag works; pinch zoom depends on browser.</span>
  <button id="zoomIn">+</button>
  <button id="zoomOut">−</button>
  <button id="reset">Reset</button>
  <button id="undo">Undo</button>
  <button id="save">Save JSON</button>
  <button id="clear">Clear</button>
  <span id="status" class="chip">0 points</span>
</div>
<div id="wrap"><canvas id="canvas"></canvas></div>

<script>
const imgSrc = "data:image/png;base64,IMG_B64";
const image = new Image(); image.src = imgSrc;

const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');

let W=0, H=0, imgW=0, imgH=0;
let scale=1, minScale=0.2, maxScale=12, tx=0, ty=0;
let dragging=false, lastX=0, lastY=0;

let points = []; // [{px, py, lat, lon}]
const statusEl = document.getElementById('status');
function setStatus(){ statusEl.textContent = points.length + " points"; }

function resize(){
  const r = canvas.parentElement.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  W = canvas.width = Math.floor(r.width * dpr);
  H = canvas.height = Math.floor(r.height * dpr);
  canvas.style.width = r.width + "px";
  canvas.style.height = r.height + "px";
  draw();
}
window.addEventListener('resize', resize);

function fitToScreen(){
  if(!imgW||!imgH) return;
  const sx = W/imgW, sy = H/imgH;
  scale = Math.min(sx, sy)*0.95;
  tx = (W - imgW*scale)/2;
  ty = (H - imgH*scale)/2;
}

function screenToImage(x,y){ return [(x - tx)/scale, (y - ty)/scale]; }

function draw(){
  ctx.save();
  ctx.clearRect(0,0,W,H);
  ctx.imageSmoothingEnabled = false;
  ctx.translate(tx,ty); ctx.scale(scale,scale);
  ctx.drawImage(image,0,0);
  for(const p of points){
    ctx.beginPath();
    ctx.arc(p.px, p.py, 6/Math.max(scale,0.5), 0, Math.PI*2);
    ctx.fillStyle='rgba(255,235,59,0.9)'; ctx.strokeStyle='#000';
    ctx.lineWidth = 2/Math.max(scale,0.5);
    ctx.fill(); ctx.stroke();
  }
  ctx.restore();
}

canvas.addEventListener('mousedown', e=>{ dragging=true; lastX=e.clientX; lastY=e.clientY; });
window.addEventListener('mouseup', ()=> dragging=false);
window.addEventListener('mousemove', e=>{
  if(!dragging) return;
  const dpr = window.devicePixelRatio || 1;
  tx += (e.clientX-lastX)*dpr; ty += (e.clientY-lastY)*dpr;
  lastX=e.clientX; lastY=e.clientY; draw();
});

canvas.addEventListener('touchstart', e=>{
  if(e.touches.length===1){ dragging=true; lastX=e.touches[0].clientX; lastY=e.touches[0].clientY; }
},{passive:false});
canvas.addEventListener('touchmove', e=>{
  if(dragging && e.touches.length===1){
    const dpr = window.devicePixelRatio || 1;
    tx += (e.touches[0].clientX-lastX)*dpr; ty += (e.touches[0].clientY-lastY)*dpr;
    lastX=e.touches[0].clientX; lastY=e.touches[0].clientY; draw();
  }
},{passive:false});
canvas.addEventListener('touchend', ()=> dragging=false);

canvas.addEventListener('wheel', e=>{
  e.preventDefault();
  const r = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const cx = (e.clientX - r.left) * dpr;
  const cy = (e.clientY - r.top)  * dpr;
  const [ix,iy] = screenToImage(cx,cy);
  const ns = Math.min(maxScale, Math.max(minScale, scale * (1 + Math.sign(e.deltaY)*-0.1)));
  scale = ns; tx = cx - ix*scale; ty = cy - iy*scale; draw();
},{passive:false});

canvas.addEventListener('click', e=>{
  if(Math.abs(e.clientX-lastX)>2 || Math.abs(e.clientY-lastY)>2) return; // was a drag
  const r = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const cx = (e.clientX - r.left)*dpr, cy = (e.clientY - r.top)*dpr;
  const [ix,iy] = screenToImage(cx,cy);
  const latStr = prompt("Latitude (decimal degrees):");
  const lonStr = prompt("Longitude (decimal degrees):");
  if(latStr===null || lonStr===null) return;
  const lat = parseFloat(latStr), lon = parseFloat(lonStr);
  if(!Number.isFinite(lat) || !Number.isFinite(lon)) return alert("Invalid lat/lon");
  points.push({px:ix, py:iy, lat:lat, lon:lon}); setStatus(); draw();
});

document.getElementById('reset').onclick = ()=>{ fitToScreen(); draw(); };
document.getElementById('undo').onclick  = ()=>{ points.pop(); setStatus(); draw(); };
document.getElementById('clear').onclick = ()=>{ points = []; setStatus(); draw(); };
document.getElementById('zoomIn').onclick = ()=>{ scale = Math.min(maxScale, scale*1.2); draw(); };
document.getElementById('zoomOut').onclick= ()=>{ scale = Math.max(minScale, scale/1.2); draw(); };
document.getElementById('save').onclick   = ()=>{
  const blob = new Blob([JSON.stringify(points, null, 2)], {type:"application/json"});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
  a.download = "tn_gcps.json"; a.click(); URL.revokeObjectURL(a.href);
};

image.onload = ()=>{ imgW=image.naturalWidth; imgH=image.naturalHeight; resize(); fitToScreen(); draw(); };
</script>
</body>
</html>
"""

html = (template
        .replace("IMG_B64", img_b64)
        .replace("PAGE_TITLE", PAGE_TITLE))

OUT_HTML.write_text(html, encoding="utf-8")
print(f"Wrote {OUT_HTML.resolve()}")
try:
    webbrowser.open(OUT_HTML.resolve().as_uri())
except Exception:
    pass


# # === Browser-based GCP picker (Tamil Nadu & other maps) ===
# 
# **What this cell does**
# - Opens a self-contained HTML viewer (`tn_gcp_picker.html`) for your geology map image.
# - Lets you **pan/zoom**, **click to drop Ground Control Points (GCPs)**, enter **lat/lon**, and **download** them as `tn_gcps.json`.
# - No server or external JS libs — everything runs locally in your browser.
# 
# ---
# 
# ## Quick start
# 1. **Set your image path** at the top of the cell:
#    ```python
#    TN_IMG_PATH = Path("overlays/tamilnadu_geology_clean.png")
# 

# In[6]:


# === Inspect GCPs, fit transforms robustly, then render BOTH overlays + wavepaths (inline) ===
import json
from pathlib import Path
import numpy as np
import pandas as pd
from PIL import Image
import matplotlib.pyplot as plt
import folium

# ---------- paths (edit if yours differ) ----------
DOWNLOADS = Path(r"C:\Users\gargi\Downloads")
TN_GCPS = DOWNLOADS / "tn_gcps.json"
SL_GCPS = DOWNLOADS / "sl_gcps.json"

TN_IMG = Path("overlays/tamilnadu_geology_clean.png")
SL_IMG = Path("overlays/srilanka_geology_clean_noblue.png")
# --------------------------------------------------

# station + two events
PALK = {"lat": 9.153, "lon": 79.875}
events = [
    {"name": "2011", "lat": 11.196, "lon": 79.250},
    {"name": "2012", "lat": 11.245, "lon": 78.581},
]

# ---------------- helpers ----------------
def load_gcps_df(fp: Path) -> pd.DataFrame:
    """Load JSON -> DataFrame with px,py,lat,lon and sanity flags."""
    pts = json.loads(fp.read_text(encoding="utf-8"))
    df = pd.DataFrame(pts)
    for c in ("px", "py", "lat", "lon"):
        if c not in df.columns:
            df[c] = np.nan
    df = df[["px", "py", "lat", "lon"]].astype(float)

    # flags: obvious lat/lon swap near India/Sri Lanka area
    df["looks_swapped"] = df["lat"].between(70, 90) & df["lon"].between(0, 20)
    df["lat_oob"] = ~df["lat"].between(-90, 90)
    df["lon_oob"] = ~df["lon"].between(-180, 180)
    return df

def apply_swaps(df: pd.DataFrame) -> pd.DataFrame:
    """Swap lat/lon where they look flipped."""
    df = df.copy()
    idx = df["looks_swapped"]
    df.loc[idx, ["lat", "lon"]] = df.loc[idx, ["lon", "lat"]].to_numpy()
    return df

def fit_affine_return_aligned(df: pd.DataFrame, hint=None):
    """
    Fit homogeneous affine: [px,py,1]^T = H @ [lon,lat,1]^T
    Robustly drop outliers. Return H, Hinv, stats, and Series residuals/used aligned to df.index.
    """
    # filter by geographic hint (broad box)
    d = df.copy()
    if hint is not None:
        lon_min, lon_max, lat_min, lat_max = hint
        d = d[d["lon"].between(lon_min, lon_max) & d["lat"].between(lat_min, lat_max)]

    if len(d) < 3:
        raise ValueError("Need ≥3 valid GCPs to fit the transform.")

    A = np.c_[d["lon"].values, d["lat"].values, np.ones(len(d))]
    bx = d["px"].values
    by = d["py"].values

    # initial fit
    Mx, *_ = np.linalg.lstsq(A, bx, rcond=None)
    My, *_ = np.linalg.lstsq(A, by, rcond=None)
    def build_H(Mx, My):
        return np.array([[Mx[0], Mx[1], Mx[2]],
                         [My[0], My[1], My[2]],
                         [0.0,   0.0,   1.0 ]], float)

    H = build_H(Mx, My)
    pred_px = A @ Mx
    pred_py = A @ My
    res = np.sqrt((pred_px - bx) ** 2 + (pred_py - by) ** 2)

    keep = np.ones(len(d), dtype=bool)
    # iteratively drop top 10% worst until median error ≤ 5 px or max 5 rounds
    for _ in range(5):
        if keep.sum() < 3:
            break
        med = float(np.median(res[keep]))
        if med <= 5.0:
            break
        thr = float(np.quantile(res[keep], 0.90))
        keep = keep & (res <= thr)

        A_k, bx_k, by_k = A[keep], bx[keep], by[keep]
        Mx, *_ = np.linalg.lstsq(A_k, bx_k, rcond=None)
        My, *_ = np.linalg.lstsq(A_k, by_k, rcond=None)
        H = build_H(Mx, My)
        pred_px = A @ Mx
        pred_py = A @ My
        res = np.sqrt((pred_px - bx) ** 2 + (pred_py - by) ** 2)

    stats = {
        "n_gcps_used": int(keep.sum()),
        "median_px_error": float(np.median(res[keep])),
        "max_px_error": float(np.max(res[keep])),
    }

    # align back to original df length
    residuals = pd.Series(np.nan, index=df.index)
    used      = pd.Series(False, index=df.index)
    residuals.loc[d.index] = res
    used.loc[d.index] = keep

    return H, np.linalg.inv(H), stats, residuals, used

def px_to_lonlat(px, py, Hinv):
    v = np.array([px, py, 1.0], float)
    lon, lat, _ = Hinv @ v
    return float(lon), float(lat)

def image_bounds(img_path: Path, Hinv):
    w, h = Image.open(img_path).size
    corners = [(0, 0), (w - 1, 0), (w - 1, h - 1), (0, h - 1)]
    ll = [px_to_lonlat(x, y, Hinv) for x, y in corners]
    lons = [c[0] for c in ll]; lats = [c[1] for c in ll]
    return [[min(lats), min(lons)], [max(lats), max(lons)]]

def union_bounds(b1, b2):
    return [[min(b1[0][0], b2[0][0]), min(b1[0][1], b2[0][1])],
            [max(b1[1][0], b2[1][0]), max(b1[1][1], b2[1][1])]]

# ---------------- 1) load GCPs + flags ----------------
tn_df = load_gcps_df(TN_GCPS)
sl_df = load_gcps_df(SL_GCPS)
display(pd.concat({"TN_GCPs": tn_df, "SL_GCPs": sl_df}, axis=1))

# ---------------- 2) auto-swap obvious flips ----------------
tn_df2 = apply_swaps(tn_df)
sl_df2 = apply_swaps(sl_df)

# ---------------- 3) quick visual check in image pixel space ----------------
fig, ax = plt.subplots(1, 2, figsize=(14, 6))
ax[0].imshow(Image.open(TN_IMG)); ax[0].scatter(tn_df2["px"], tn_df2["py"], s=40, c="yellow", edgecolor="k")
ax[0].set_title("Tamil Nadu GCPs"); ax[0].axis("off")
ax[1].imshow(Image.open(SL_IMG)); ax[1].scatter(sl_df2["px"], sl_df2["py"], s=40, c="yellow", edgecolor="k")
ax[1].set_title("Sri Lanka GCPs"); ax[1].axis("off")
plt.tight_layout(); plt.show()

# ---------------- 4) fit transforms (robust) ----------------
tn_hint = (74, 88, 6, 16)   # lon_min, lon_max, lat_min, lat_max
sl_hint = (78, 84, 4, 11)

H_TN, Hinv_TN, tn_stats, tn_resid, tn_used = fit_affine_return_aligned(tn_df2, hint=tn_hint)
H_SL, Hinv_SL, sl_stats, sl_resid, sl_used = fit_affine_return_aligned(sl_df2, hint=sl_hint)

print("TN stats:", tn_stats)
print("SL stats:", sl_stats)

tn_df2 = tn_df2.assign(residual_px=tn_resid, used=tn_used)
sl_df2 = sl_df2.assign(residual_px=sl_resid, used=sl_used)

display(pd.concat({
    "TN_residuals": tn_df2[["px","py","lat","lon","residual_px","used"]],
    "SL_residuals": sl_df2[["px","py","lat","lon","residual_px","used"]],
}, axis=1))

# ---------------- 5) compute bounds, render overlays + paths inline ----------------
bounds_TN = image_bounds(TN_IMG, Hinv_TN)
bounds_SL = image_bounds(SL_IMG, Hinv_SL)
print("TN bounds:", bounds_TN)
print("SL bounds:", bounds_SL)

both_bounds = union_bounds(bounds_TN, bounds_SL)
center = [(both_bounds[0][0] + both_bounds[1][0]) / 2,
          (both_bounds[0][1] + both_bounds[1][1]) / 2]

m = folium.Map(location=center, zoom_start=6, tiles="CartoDB positron")
folium.raster_layers.ImageOverlay(image=str(TN_IMG), bounds=bounds_TN, opacity=0.70,
                                  name="Tamil Nadu geology").add_to(m)
folium.raster_layers.ImageOverlay(image=str(SL_IMG), bounds=bounds_SL, opacity=0.70,
                                  name="Sri Lanka geology").add_to(m)

folium.Marker([PALK["lat"], PALK["lon"]], tooltip="II.PALK").add_to(m)
for ev in events:
    folium.PolyLine([(PALK["lat"], PALK["lon"]), (ev["lat"], ev["lon"])],
                    color="#FF3B3B", weight=3, opacity=0.95,
                    tooltip=f"Wavepath to {ev['name']}").add_to(m)
    folium.Marker([ev["lat"], ev["lon"]], tooltip=f"EQ {ev['name']}").add_to(m)

folium.LayerControl().add_to(m)
m.fit_bounds(both_bounds)
m


# # === Inspect GCPs → Fit Affine Transforms (robust) → Render BOTH overlays + wavepaths ===
# 
# **What this cell does**
# - Loads your clicked **GCPs** (`tn_gcps.json`, `sl_gcps.json`) and runs quick **sanity checks** (OOB coords, likely lat/lon swaps).
# - Fits a **homogeneous affine transform** per map:  
#   \[px, py, 1]^T = **H** · \[lon, lat, 1]^T, with **robust outlier rejection**.
# - Reports **residual errors** (px) and which GCPs were **used/dropped**.
# - Computes **geographic bounds** of each image from **H⁻¹** and renders:
#   - **Both geology overlays** (Tamil Nadu + Sri Lanka) as `ImageOverlay`
#   - **II.PALK** station and **wavepaths** to 2011 & 2012 events
# - Displays an interactive **Folium** map (pan/zoom, layer toggle).
# 
# ---
# 
# ## Inputs & paths
# - Edit these if your files differ:
#   ```python
#   DOWNLOADS = Path(r"C:\Users\gargi\Downloads")
#   TN_GCPS = DOWNLOADS / "tn_gcps.json"
#   SL_GCPS = DOWNLOADS / "sl_gcps.json"
# 
#   TN_IMG = Path("overlays/tamilnadu_geology_clean.png")
#   SL_IMG = Path("overlays/srilanka_geology_clean_noblue.png")
# 

# In[3]:


# === Build "formation ↔ color" tables by typing entries ===
# - For each map, you'll be prompted: formation name, then color.
# - Color can be "#RRGGBB" or "R,G,B" (e.g., 234,192,115).
# - Type "undo" for the name to pop the last row; leave name blank to finish that map.

from pathlib import Path
import re
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

SAVE_DIR = Path(".")     # change if you want to save somewhere else
TN_OUT   = SAVE_DIR / "formations_TN_colors.csv"
SL_OUT   = SAVE_DIR / "formations_SL_colors.csv"

HEX_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")

def parse_color(s):
    s = s.strip()
    # hex: "#AABBCC" or "AABBCC"
    if HEX_RE.match(s if s.startswith("#") else "#"+s):
        hx = s if s.startswith("#") else "#"+s
        r = int(hx[1:3], 16); g = int(hx[3:5], 16); b = int(hx[5:7], 16)
        return (r,g,b), hx.upper()
    # rgb: "r,g,b" or "r b g" etc.
    parts = re.split(r"[,\s]+", s)
    parts = [p for p in parts if p != ""]
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        r,g,b = [max(0, min(255, int(p))) for p in parts]
        return (r,g,b), f"#{r:02X}{g:02X}{b:02X}"
    raise ValueError("Color must be #RRGGBB or R,G,B (0–255).")

def prompt_table(map_name, outfile):
    print(f"\n--- {map_name}: enter formation + color ---")
    print(" Tip: color as #RRGGBB or R,G,B   | type 'undo' as the name to remove last row | blank name to finish\n")
    rows = []
    while True:
        name = input("Formation name: ").strip()
        if name == "":
            break
        if name.lower() == "undo":
            if rows:
                removed = rows.pop()
                print(f"  (undid) {removed['formation']} {removed['color_hex']}")
            else:
                print("  (nothing to undo)")
            continue
        try:
            col = input("Color (#RRGGBB or R,G,B): ").strip()
            (r,g,b), hx = parse_color(col)
        except Exception as e:
            print(f"  ! {e}")
            continue
        rows.append({"map": map_name, "formation": name, "color_hex": hx, "R": r, "G": g, "B": b})
        print(f"  ✓ added: {name}  {hx}  ({r},{g},{b})\n")

    df = pd.DataFrame(rows, columns=["map","formation","color_hex","R","G","B"])
    if df.empty:
        print(f"(no entries for {map_name})")
        return df

    # save + preview
    df.to_csv(outfile, index=False)
    print(f"\nSaved {len(df)} rows → {outfile.resolve()}")

    # quick swatch preview
    fig, ax = plt.subplots(figsize=(6, max(2, 0.35*len(df))))
    ax.set_xlim(0, 1); ax.set_ylim(0, len(df))
    ax.axis("off")
    for i, row in df.reset_index(drop=True).iterrows():
        ax.add_patch(Rectangle((0.02, i+0.15), 0.1, 0.7,
                               facecolor=(row["R"]/255, row["G"]/255, row["B"]/255), edgecolor="k"))
        ax.text(0.15, i+0.5, f"{row['formation']}   {row['color_hex']}  ({row['R']},{row['G']},{row['B']})",
                va="center", fontsize=10)
    ax.set_title(f"{map_name} legend colors", fontsize=12)
    plt.gca().invert_yaxis()
    plt.tight_layout(); plt.show()

    display(df)
    return df

# Run for both maps (you can comment one out if you want to do them separately)
df_tn = prompt_table("Tamil Nadu", TN_OUT)
df_sl = prompt_table("Sri Lanka",  SL_OUT)



# # === Formation ↔ Color Tables ===  
# 
# This cell lets you **build custom legend tables** for each geology map by typing in formation names and their colors. You’ll be prompted interactively to enter a **formation name** and its **color** (in `#RRGGBB` or `R,G,B` format). Use `"undo"` to remove the last entry or leave the name blank to finish. Once done, the script saves your entries to CSV (`formations_TN_colors.csv` / `formations_SL_colors.csv`) and shows a quick **color swatch preview** for verification.  
# 

# **How to use**
# 
# * Run the cell → type entries one by one.
# * Color can be `#C07CC0` or `192,124,192`.
# * Type **undo** as the formation name to remove the last row.
# * Hit **Enter** on an empty formation name to finish.
# * You’ll get a color-swatch preview and two CSVs you can reuse later.
# 

# In[16]:


# === Combine Tamil Nadu + Sri Lanka legend tables and add estimated Vp ===
from pathlib import Path
import pandas as pd
import re

# If you ran the previous cell, these paths should exist already.
SAVE_DIR = Path(".")
TN_CSV = Path.home() / "formations_TN_colors.csv"   # change if you saved elsewhere
SL_CSV = Path.home() / "formations_SL_colors.csv"   # change if you saved elsewhere

# Fallback to local folder if the Home paths don't exist
if not TN_CSV.exists():
    TN_CSV = SAVE_DIR / "formations_TN_colors.csv"
if not SL_CSV.exists():
    SL_CSV = SAVE_DIR / "formations_SL_colors.csv"

df_tn = pd.read_csv(TN_CSV)
df_sl = pd.read_csv(SL_CSV)
df = pd.concat([df_tn, df_sl], ignore_index=True)

# --- Vp estimator (very rough, km/s). Tweak as you learn more locally. ---
# We match by simple keywords in the formation name.
# Add/modify rules below as needed.
VP_RULES = [
    # (regex pattern, Vp_min, Vp_max)  [km/s]
    (r"alluv(ium|ial)|lagoon|coastal", 1.8, 3.2),              # unconsolidated/saturated sediments
    (r"cuddalore|sand|silt|gravel", 2.5, 4.2),                 # Cuddalore Fm: sandy–silty, compacted
    (r"limestone|calcarenite", 5.0, 6.5),                      # Miocene limestone
    (r"migmati|gneiss|granite|crystalline", 5.8, 6.5),         # migmatites / felsic crystalline
]

def estimate_vp_kms(formation_name: str):
    name = formation_name.lower()
    for patt, vmin, vmax in VP_RULES:
        if re.search(patt, name):
            return vmin, vmax
    # default if nothing matched (generic sedimentary)
    return 2.0, 3.5

vp_min, vp_max = [], []
for n in df["formation"]:
    vmin, vmax = estimate_vp_kms(n)
    vp_min.append(vmin)
    vp_max.append(vmax)

df["Vp_min_km_s"] = vp_min
df["Vp_max_km_s"] = vp_max
df["Vp_mid_km_s"] = df[["Vp_min_km_s","Vp_max_km_s"]].mean(axis=1)
df["Vp_mid_m_s"]  = (df["Vp_mid_km_s"] * 1000).round().astype(int)

# Save + show
OUT = SAVE_DIR / "formations_combined_with_Vp.csv"
df.to_csv(OUT, index=False)
print(f"Saved → {OUT.resolve()}")
display(df)


# # === Combine legends + add rough Vp ===
# This cell loads the **Tamil Nadu** and **Sri Lanka** legend CSVs, merges them, and attaches **rough P-wave velocity (Vp) estimates** per formation using simple **keyword rules** (regex). For each row it assigns a Vp **min/max** (km/s), computes a **midpoint** (km/s) and its **m/s** equivalent, then writes the result to `formations_combined_with_Vp.csv` and displays the table. Tweak `VP_RULES` to refine ranges as you learn local rock speeds (e.g., limestone vs. gneiss vs. unconsolidated sediments).
# 

# In[17]:


# === Partition each wavepath into segments: per-formation vs WATER ===
# Requires:
#   - H_TN, H_SL (affines lon/lat -> px/py) and TN_IMG, SL_IMG from your previous cell
#   - bounds_TN, bounds_SL, PALK, events (same as your mapping cell)
#   - formations_combined_with_Vp.csv (has columns: formation, R,G,B)
from pathlib import Path
import numpy as np
import pandas as pd
from PIL import Image
from shapely.geometry import Polygon, LineString, Point
from pyproj import Geod

SAVE_DIR = Path(".")
FORMATIONS_CSV = SAVE_DIR / "formations_combined_with_Vp.csv"

# Load legend (formation ↔ RGB)
legend = pd.read_csv(FORMATIONS_CSV)
rgb2name = {(int(r), int(g), int(b)): name for name, r, g, b
            in legend[["formation","R","G","B"]].itertuples(index=False)}

# Build polygons for overlay extents (lon/lat)
poly_TN = Polygon([(bounds_TN[0][1], bounds_TN[0][0]),
                   (bounds_TN[1][1], bounds_TN[0][0]),
                   (bounds_TN[1][1], bounds_TN[1][0]),
                   (bounds_TN[0][1], bounds_TN[1][0])])

poly_SL = Polygon([(bounds_SL[0][1], bounds_SL[0][0]),
                   (bounds_SL[1][1], bounds_SL[0][0]),
                   (bounds_SL[1][1], bounds_SL[1][0]),
                   (bounds_SL[0][1], bounds_SL[1][0])])

# Open overlay images (RGB)
img_TN = Image.open(TN_IMG).convert("RGB")
img_SL = Image.open(SL_IMG).convert("RGB")
W_TN, H_TN_px = img_TN.size
W_SL, H_SL_px = img_SL.size

# Helper: lon/lat -> pixel in a given image using affine H (px,py,1)^T = H @ (lon,lat,1)^T
def lonlat_to_pxpy(lon, lat, H):
    v = np.array([lon, lat, 1.0], float)
    px, py, _ = H @ v
    return float(px), float(py)

# Sample at ~250 m spacing along the great-circle segment
GEOD = Geod(ellps="WGS84")

def densify_points(lat1, lon1, lat2, lon2, step_m=250.0):
    # total distance
    _, _, dist_m = GEOD.inv(lon1, lat1, lon2, lat2)
    nsteps = int(max(1, np.ceil(dist_m / step_m)))
    lats = np.linspace(lat1, lat2, nsteps + 1)
    lons = np.linspace(lon1, lon2, nsteps + 1)
    return list(zip(lats, lons))

def nearest_formation(rgb, max_tol=12):
    # exact match first
    if rgb in rgb2name:
        return rgb2name[rgb]
    # nearest within tolerance (handles anti-aliased edges)
    best, bestd = None, 1e9
    r0, g0, b0 = rgb
    for (r,g,b), name in rgb2name.items():
        d = (r-r0)**2 + (g-g0)**2 + (b-b0)**2
        if d < bestd:
            best, bestd = name, d
    if best is not None and bestd <= max_tol**2:
        return best
    return "Unknown"

def classify_point(lat, lon):
    p = Point(lon, lat)
    if poly_TN.contains(p):
        px, py = lonlat_to_pxpy(lon, lat, H_TN)
        if 0 <= px < W_TN and 0 <= py < H_TN_px:
            rgb = img_TN.getpixel((int(round(px)), int(round(py))))
            return nearest_formation(rgb)
    if poly_SL.contains(p):
        px, py = lonlat_to_pxpy(lon, lat, H_SL)
        if 0 <= px < W_SL and 0 <= py < H_SL_px:
            rgb = img_SL.getpixel((int(round(px)), int(round(py))))
            return nearest_formation(rgb)
    # outside both overlays ⇒ treat as WATER
    return "Water"

def segment_wavepath(event_name, ev_lat, ev_lon, station_lat, station_lon, step_m=250.0):
    pts = densify_points(station_lat, station_lon, ev_lat, ev_lon, step_m=step_m)
    labels = [classify_point(lat, lon) for lat, lon in pts]

    # Build contiguous segments with geodesic lengths
    segments = []
    seg_label = labels[0]
    seg_start = pts[0]
    seg_len_m = 0.0

    for i in range(1, len(pts)):
        latA, lonA = pts[i-1]
        latB, lonB = pts[i]
        _, _, dAB = GEOD.inv(lonA, latA, lonB, latB)
        seg_len_m += dAB
        if labels[i] != seg_label:
            segments.append({"event": event_name,
                             "start_lat": seg_start[0], "start_lon": seg_start[1],
                             "end_lat": latA, "end_lon": lonA,
                             "label": seg_label,
                             "length_km": seg_len_m/1000.0})
            # start a new segment
            seg_label = labels[i]
            seg_start = (latB, lonB)
            seg_len_m = 0.0

    # close last segment
    latA, lonA = pts[-2]
    latB, lonB = pts[-1]
    _, _, dAB = GEOD.inv(lonA, latA, lonB, latB)
    seg_len_m += dAB
    segments.append({"event": event_name,
                     "start_lat": seg_start[0], "start_lon": seg_start[1],
                     "end_lat": latB, "end_lon": lonB,
                     "label": seg_label,
                     "length_km": seg_len_m/1000.0})

    seg_df = pd.DataFrame(segments)
    totals = seg_df.groupby("label", as_index=False)["length_km"].sum().sort_values("length_km", ascending=False)
    return seg_df, totals

# ---- Run for both events ----
all_segs = []
all_totals = []
for ev in events:
    seg_df, totals = segment_wavepath(ev["name"], ev["lat"], ev["lon"], PALK["lat"], PALK["lon"], step_m=250.0)
    print(f"\n=== Ordered segments for event {ev['name']} ===")
    display(seg_df[["label","length_km"]])
    print(f"--- Totals for {ev['name']} ---")
    display(totals)
    seg_df["event"] = ev["name"]
    totals["event"] = ev["name"]
    all_segs.append(seg_df)
    all_totals.append(totals)

segments_all = pd.concat(all_segs, ignore_index=True)
totals_all   = pd.concat(all_totals, ignore_index=True)


# # === Partition wavepaths by formation (with WATER outside overlays) ===  
# This cell samples each **PALK → event** great-circle path at ~250 m intervals, classifies every point to a **map formation** by reading the underlying pixel color (Tamil Nadu / Sri Lanka overlays) using the fitted affines `H_TN` / `H_SL`, and merges adjacent points with the same label into **contiguous segments** with geodesic **lengths (km)**. Colors are matched to the legend (`formations_combined_with_Vp.csv`) with a small tolerance to handle anti-aliasing; points falling off both overlays are labeled **Water** and unmatched colors become **Unknown**. It prints per-event **ordered segments** and a **totals-by-formation** table, and concatenates results into `segments_all` and `totals_all` for downstream use.  
# 

# In[18]:


# === Point the last cell to your P-pick table ===
from pathlib import Path
import pandas as pd
import numpy as np

# If the table is still in memory, use it; otherwise load from disk.
if "summary_df" in globals():
    _picks_df = summary_df.copy()
else:
    # this is the file shown in your screenshot
    PICKS_CSV = Path("waveforms/earthquake_summary_with_velocity.csv")
    if not PICKS_CSV.exists():
        # fallbacks, just in case
        for alt in [
            Path("waveforms/earthquake_summary.csv"),
            Path("earthquake_summary_with_velocity.csv"),
            Path("picks.csv"),
        ]:
            if alt.exists():
                PICKS_CSV = alt
                break
    _picks_df = pd.read_csv(PICKS_CSV)

# Normalize and keep only what we need
need_cols = {"Event", "Offset_Seconds"}
_missing = need_cols - set(_picks_df.columns)
if _missing:
    raise ValueError(f"P-picks table is missing columns: {_missing}. "
                     f"Found: {list(_picks_df.columns)}")

picks = _picks_df[["Event", "Offset_Seconds"]].copy()
picks["Event"] = picks["Event"].astype(str).str.strip()
picks["Offset_Seconds"] = pd.to_numeric(picks["Offset_Seconds"], errors="coerce")

# Build the dict your last cell expects
T_obs = (picks.groupby("Event", as_index=True)["Offset_Seconds"]
               .mean()
               .to_dict())

print("✅ P-picks ready for last cell:", T_obs)


# # === Load & normalize P-pick table for travel-time dict (T_obs) ===  
# This cell grabs your P-pick summary (from `summary_df` in-memory or a CSV fallback), validates the required columns (`Event`, `Offset_Seconds`), cleans types, and computes the **mean P-arrival offset per event**. It then builds `T_obs`, a simple `{event_name: mean_offset_seconds}` dictionary that the previous wavepath/segmentation cell can use for travel-time comparisons. If columns are missing, it raises a clear error so you can fix the source table.
# 

# In[19]:


# === SETUP for Vp-of-Water solver (place this cell RIGHT BEFORE your last cell) ===
from pathlib import Path
import pandas as pd
import numpy as np

# --------------------------
# 1) Hardcode input file paths
# --------------------------
FORMATIONS_CSV = Path("formations_combined_with_Vp.csv")
PICKS_CSV      = Path("waveforms/earthquake_summary_with_velocity.csv")  # has Event, Offset_Seconds
SEGMENTS_PATH  = Path("segments_all.csv")  # change to your actual segments file if different

# --------------------------
# 2) LEGEND (formations + Vp ranges)
# --------------------------
if not FORMATIONS_CSV.exists():
    raise FileNotFoundError(f"Legend CSV not found: {FORMATIONS_CSV.resolve()}")
legend = pd.read_csv(FORMATIONS_CSV)

need_legend = {"formation", "Vp_min_km_s", "Vp_mid_km_s", "Vp_max_km_s"}
miss = need_legend - set(legend.columns)
if miss:
    raise ValueError(f"Legend CSV missing columns: {sorted(miss)}")

for c in ["Vp_min_km_s", "Vp_mid_km_s", "Vp_max_km_s"]:
    legend[c] = pd.to_numeric(legend[c], errors="coerce")

# maps used by last cell
vp_min_map = dict(zip(legend["formation"], legend["Vp_min_km_s"]))
vp_mid_map = dict(zip(legend["formation"], legend["Vp_mid_km_s"]))
vp_max_map = dict(zip(legend["formation"], legend["Vp_max_km_s"]))

def vp_of(label, which="mid"):
    d = {"min": vp_min_map, "mid": vp_mid_map, "max": vp_max_map}[which]
    return d.get(label, np.nan)

# --------------------------
# 3) P-WAVE PICKS (Event, Offset_Seconds)
#    Prefer in-memory 'summary_df'; otherwise load from CSV you made.
# --------------------------
if "summary_df" in globals():
    picks_df = summary_df.copy()
else:
    if not PICKS_CSV.exists():
        raise FileNotFoundError(f"Picks CSV not found: {PICKS_CSV.resolve()}")
    picks_df = pd.read_csv(PICKS_CSV)

need_picks = {"Event", "Offset_Seconds"}
miss = need_picks - set(picks_df.columns)
if miss:
    raise ValueError(f"Picks table missing columns: {sorted(miss)}; found {list(picks_df.columns)}")

picks_df = picks_df[["Event", "Offset_Seconds"]].copy()
picks_df["Event"] = picks_df["Event"].astype(str).str.strip()
picks_df["Offset_Seconds"] = pd.to_numeric(picks_df["Offset_Seconds"], errors="coerce")

# dict the last cell expects
T_obs = (picks_df.groupby("Event", as_index=True)["Offset_Seconds"]
                 .mean()
                 .to_dict())

# --------------------------
# 4) SEGMENTS (event, label, length_km)
#    Prefer in-memory 'segments_all'; otherwise load from disk.
# --------------------------
def _load_segments_csv_or_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Segments file not found: {path.resolve()}")
    if path.suffix.lower() == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)
    # normalize names
    cols = {c.lower(): c for c in df.columns}
    req = {"event", "label", "length_km"}
    if not req.issubset(set(cols)):
        raise ValueError(f"Segments missing columns {sorted(req - set(cols))}; found {list(df.columns)}")
    df = df.rename(columns={
        cols["event"]: "event",
        cols["label"]: "label",
        cols["length_km"]: "length_km"
    })
    df["event"] = df["event"].astype(str).str.strip()
    df["label"] = df["label"].astype(str).str.strip()
    df["length_km"] = pd.to_numeric(df["length_km"], errors="coerce")
    df = df[np.isfinite(df["length_km"]) & (df["length_km"] > 0)].copy()
    return df

if "segments_all" not in globals():
    segments_all = _load_segments_csv_or_parquet(SEGMENTS_PATH)

# --------------------------
# 5) Quick sanity print
# --------------------------
print("✅ Inputs ready")
print("  FORMATIONS_CSV:", FORMATIONS_CSV)
print("  PICKS source   :", "summary_df (memory)" if "summary_df" in globals() else PICKS_CSV)
print("  SEGMENTS source:", "segments_all (memory)" if "segments_all" in globals() else SEGMENTS_PATH)
print("  Legend rows    :", len(legend))
print("  Picks events   :", len(T_obs))
print("  Segments rows  :", len(segments_all))
print("  Events in segments:", sorted(segments_all['event'].unique()))


# In[ ]:





# In[20]:


# === Save Vp-of-Water results ===
from pathlib import Path
import pandas as pd
from datetime import datetime

OUT_DIR = Path("waveforms")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Clean up display precision (optional)
save_df = water_report.copy()
num_cols = save_df.select_dtypes(include="number").columns
save_df[num_cols] = save_df[num_cols].round(4)

# Stable filename + timestamped archive
stable_path = OUT_DIR / "water_velocity_estimates.csv"
timestamped = OUT_DIR / f"water_velocity_estimates_{datetime.now():%Y%m%d_%H%M%S}.csv"

save_df.to_csv(stable_path, index=False)
save_df.to_csv(timestamped, index=False)

print("✅ Saved:")
print(" -", stable_path)
print(" -", timestamped)


# In[25]:


# === Estimate Vp for the single 'Water/Unknown' segment (>=100 km) for each event ===
from pathlib import Path
import pandas as pd
import numpy as np

# If vp_of isn't defined yet (safety)
if "vp_of" not in globals():
    vp_min_map = dict(zip(legend["formation"], legend["Vp_min_km_s"]))
    vp_mid_map = dict(zip(legend["formation"], legend["Vp_mid_km_s"]))
    vp_max_map = dict(zip(legend["formation"], legend["Vp_max_km_s"]))
    def vp_of(label, which="mid"):
        d = {"min": vp_min_map, "mid": vp_mid_map, "max": vp_max_map}[which]
        return d.get(label, np.nan)

# Only these labels are considered "water candidates"
water_labels = {"Water", "Unknown"}

MIN_WATER_KM = 80.0  # threshold

def solve_water_speed(event_name: str) -> dict | None:
    segs = segments_all[segments_all["event"] == event_name].copy()
    if segs.empty or event_name not in T_obs:
        return None

    # Split candidates vs. known
    cand = segs[segs["label"].isin(water_labels)].copy()
    known = segs[~segs["label"].isin(water_labels)].copy()

    # Choose the ONE water/unknown segment: the longest candidate (if >= threshold)
    L_water = 0.0
    chosen_water_label = None
    ignored_unknown_km = 0.0
    num_unknown_segments = int(len(cand))

    if not cand.empty:
        cand = cand.sort_values("length_km", ascending=False)
        longest_len = float(cand.iloc[0]["length_km"])
        longest_lab = str(cand.iloc[0]["label"])
        if longest_len >= MIN_WATER_KM:
            L_water = longest_len
            chosen_water_label = longest_lab
        # sum all other unknown/water lengths (ignored in model)
        if len(cand) > 1:
            ignored_unknown_km = float(cand.iloc[1:]["length_km"].sum())

    # Known time through non-water segments
    def known_time(which: str) -> float:
        t = 0.0
        for _, row in known.iterrows():
            v = vp_of(row["label"], which)
            if np.isfinite(v) and v > 0:
                t += row["length_km"] / v
        return t

    T_known_min = known_time("max")  # fastest rocks
    T_known_mid = known_time("mid")
    T_known_max = known_time("min")  # slowest rocks

    T = float(T_obs[event_name])     # observed end-to-end time (s)

    def solve(T_known: float) -> float:
        # Only the chosen water segment is modeled as water.
        denom = T - T_known
        if denom <= 0 or L_water <= 0:
            return np.nan
        return L_water / denom  # km/s

    Vw_from_minKnown = solve(T_known_min)
    Vw_from_midKnown = solve(T_known_mid)
    Vw_from_maxKnown = solve(T_known_max)

    # Totals for context
    L_total_all = float(segs["length_km"].sum())
    V_avg_total = L_total_all / T if T > 0 else np.nan

    return {
        "event": event_name,
        "num_unknown_segments": num_unknown_segments,
        "chosen_water_label": chosen_water_label,
        "L_water_km": L_water,
        "ignored_unknown_km": ignored_unknown_km,
        "L_total_km": L_total_all,
        "T_obs_s": T,
        "T_known_min_s": T_known_min,
        "T_known_mid_s": T_known_mid,
        "T_known_max_s": T_known_max,
        "V_water_km_s_from_minKnown": Vw_from_minKnown,
        "V_water_km_s_from_midKnown": Vw_from_midKnown,
        "V_water_km_s_from_maxKnown": Vw_from_maxKnown,
        "V_total_avg_km_s": V_avg_total
    }

# --- run for all events ---
events_list = sorted(segments_all["event"].unique().astype(str))
rows = [res for ev in events_list if (res := solve_water_speed(ev))]

water_report = pd.DataFrame(rows)

# print compact summary
for _, r in water_report.iterrows():
    ev = r["event"]
    print(f"\n=== {ev} ===")
    print(f"Obs time: {r['T_obs_s']:.2f} s | L_total(all): {r['L_total_km']:.2f} km")
    print(f"Chosen water seg: {r['chosen_water_label']} | L_water: {r['L_water_km']:.2f} km "
          f"(ignored other unknown: {r['ignored_unknown_km']:.2f} km; n_unknown={r['num_unknown_segments']})")
    print(f"Known-time (min/mid/max): {r['T_known_min_s']:.2f} / {r['T_known_mid_s']:.2f} / {r['T_known_max_s']:.2f} s")
    print("Vp_water estimates (km/s):")
    print(f"  from min-known: {r['V_water_km_s_from_minKnown']:.2f}")
    print(f"  from mid-known: {r['V_water_km_s_from_midKnown']:.2f}")
    print(f"  from max-known: {r['V_water_km_s_from_maxKnown']:.2f}")
    print(f"Whole-path average (all): {r['V_total_avg_km_s']:.2f} km/s")

display(water_report)

# save
from datetime import datetime
outdir = Path("waveforms"); outdir.mkdir(parents=True, exist_ok=True)
water_report.round(4).to_csv(outdir / "water_velocity_estimates.csv", index=False)
water_report.round(4).to_csv(outdir / f"water_velocity_estimates_{datetime.now():%Y%m%d_%H%M%S}.csv", index=False)
print("\n✅ saved to waveforms/water_velocity_estimates*.csv")


# # === Solve & Save Vp-of-Water results ===
# This cell takes your path segmentation (`segments_all`), per-formation Vp maps (`vp_of` from the legend), and observed P-arrival times (`T_obs`) to estimate **water P-wave speed** for each event. It (1) picks the **longest** `Water/Unknown` segment ≥ **80 km** as the ocean leg, (2) computes known travel time through non-water segments using **min/mid/max** rock speeds, and (3) solves `V_water = L_water / (T_obs − T_known)`. It prints a compact per-event summary and writes a tidy report to **`waveforms/water_velocity_estimates.csv`** plus a timestamped archive. The output includes event name, chosen water label/length, ignored unknown length, totals, known-time brackets, three Vp_water estimates, and the whole-path average speed.
# 

# In[26]:


# === Diagnose why Vw is NaN or weird for each event ===
import numpy as np
import pandas as pd

water_labels = {"Water", "Unknown"}  # keep in sync with solver

def per_label_breakdown(event):
    segs = segments_all[segments_all["event"] == str(event)].copy()
    known = segs[~segs["label"].isin(water_labels)].copy()
    rows = []
    for lab, df in known.groupby("label"):
        L = df["length_km"].sum()
        v_min = vp_of(lab, "min")
        v_mid = vp_of(lab, "mid")
        v_max = vp_of(lab, "max")
        rows.append({
            "label": lab,
            "length_km": L,
            "t_min_s (v_max)": L / v_max if np.isfinite(v_max) and v_max > 0 else np.nan,  # fastest rock
            "t_mid_s": L / v_mid if np.isfinite(v_mid) and v_mid > 0 else np.nan,
            "t_max_s (v_min)": L / v_min if np.isfinite(v_min) and v_min > 0 else np.nan,  # slowest rock
            "v_min": v_min, "v_mid": v_mid, "v_max": v_max
        })
    out = pd.DataFrame(rows).sort_values("t_min_s (v_max)", ascending=False)
    return out

def diagnose_event(event):
    ev = str(event)
    segs = segments_all[segments_all["event"] == ev]
    T = float(T_obs.get(ev, np.nan))
    Lw = segs[segs["label"].isin(water_labels)]["length_km"].sum()
    known = segs[~segs["label"].isin(water_labels)]
    def kt(which):  # known time
        s = 0.0
        for _, r in known.iterrows():
            v = vp_of(r["label"], which)
            if np.isfinite(v) and v > 0:
                s += r["length_km"] / v
        return s
    tmin, tmid, tmax = kt("max"), kt("mid"), kt("min")
    print(f"\n=== DIAG {ev} ===")
    print(f"T_obs: {T:.2f} s | L_water: {Lw:.2f} km | Known time (min/mid/max): {tmin:.2f}/{tmid:.2f}/{tmax:.2f} s")
    print(f"Slack vs fastest-known: T_obs - T_known_min = {T - tmin:.2f} s")
    if T <= tmin:
        need = tmin / T if T > 0 else np.inf
        print(f"⚠️  No solution: even the fastest-known rocks exceed observed time.")
        print(f"   → You’d need rock speeds × {need:.3f} faster on average, or reduce known lengths by ~{(1-1/need)*100:.1f}%,")
        print(f"     or add ~{(tmin-T):.2f} s of slack (pick bias) to make it solvable.")
    print("\nTop known labels by time (fastest case):")
    display(per_label_breakdown(ev).head(10))

# Run for your events
for ev in sorted(segments_all['event'].unique()):
    diagnose_event(ev)


# ```markdown
# # === Diagnose Vw NaNs or odd values (per event) ===
# This cell explains **why the solved water speed (Vw)** might be **NaN** or unrealistic. For each event, it (1) computes the **known-time bracket** through non-water segments using min/mid/max rock speeds, (2) compares your **observed P time** to the **fastest-known** time to check solvability (`T_obs > T_known_min`), and (3) prints a ranked **per-label time breakdown** showing which formations dominate travel time (and their Vp ranges). If `T_obs ≤ T_known_min`, it flags the issue and quantifies how much faster rocks would need to be, how much length would need trimming, or how much **pick slack** (seconds) would make the solution feasible.
# ```
# 
# 

# In[27]:


# --- annotate feasibility and optional slack-based upper bound ---
import numpy as np

water_report["feasible_min"] = water_report["T_obs_s"] > water_report["T_known_min_s"]
water_report["feasible_mid"] = water_report["T_obs_s"] > water_report["T_known_mid_s"]
water_report["feasible_max"] = water_report["T_obs_s"] > water_report["T_known_max_s"]

# how many seconds of slack would make the slowest-rocks case solvable?
water_report["slack_needed_maxKnown_s"] = (
    water_report["T_known_max_s"] - water_report["T_obs_s"]
).clip(lower=0).round(2)

# optional: compute max-known water Vp if we allow +3 s slack on picks
SLACK = 3.0
def vmax_with_slack(row):
    denom = (row["T_obs_s"] + SLACK) - row["T_known_max_s"]
    return row["L_water_km"]/denom if (denom > 0 and row["L_water_km"] > 0) else np.nan

water_report["V_water_km_s_from_maxKnown_w_slack3"] = water_report.apply(vmax_with_slack, axis=1).round(4)

display(water_report)


# # Water/Unknown Segment Velocity Estimation
# 
# ### Overview
# We estimated the effective P-wave velocity (**Vp**) of the "Water/Unknown" path segments for the 2011 and 2012 Pondicherry earthquakes using our segmentation + velocity table.
# 
# ### Steps
# 1. **Inputs prepared**  
#    - `formations_combined_with_Vp.csv` provided min/mid/max velocity ranges for each formation.  
#    - `segments_all` contained event-wise path segments with lengths and labels.  
#    - `earthquake_summary_with_velocity.csv` (from earlier) provided observed P-wave arrival times.
# 
# 2. **Solver design**  
#    - Split each path into **known rock segments** vs **unknown/water candidates**.  
#    - Only the **longest unknown/water segment** was kept if it was ≥ 100 km; all others were ignored.  
#    - Known segments were timed using three velocity cases:  
#      - **min-known** → fastest rocks (Vp = max values).  
#      - **mid-known** → typical values.  
#      - **max-known** → slowest rocks (Vp = min values).  
#    - For each case, solve for Vp of the chosen water segment:  
#      \[
#      V_{water} = \frac{L_{water}}{T_{obs} - T_{known}}
#      \]
# 
# 3. **Diagnostics**  
#    - Early tests showed `NaN` results when the **known time alone exceeded observed time** → physically infeasible under slow-rock assumptions.  
#    - We updated `VP_RULES` to expand realistic Vp ranges (e.g., coastal sediments up to 3.2 km/s, Cuddalore up to 4.2 km/s).  
#    - Added diagnostics to check which formations dominated known-time.
# 
# 4. **Results**
#    - **2011 event**  
#      - Obs time: ~55 s  
#      - Chosen water: ~98 km (longest unknown)  
#      - Estimated Vp_water ≈ 6.7 km/s (min-known case), ~26.7 km/s (mid-known).  
#      - Max-known case remained infeasible (NaN).
#    - **2012 event**  
#      - Obs time: ~69 s  
#      - Chosen water: ~83 km  
#      - Estimated Vp_water ≈ 3.7 km/s (min-known), ~7.7 km/s (mid-known).  
#      - Max-known case also infeasible.
# 
# 5. **Interpretation**
#    - The solver now cleanly reports feasible water Vp where possible, flags infeasible slow-rock cases with `NaN`, and saves results to  
#      ```
#      waveforms/water_velocity_estimates.csv
#      ```
#    - Diagnostic columns (e.g., `feasible_min/mid/max`, `slack_needed_maxKnown_s`) help explain why certain solutions are impossible.
# 
# ---
# 
# **Next steps:**  
# - Fine-tune velocity tables using more literature values.  
# - Consider adding a small slack (~2–3 s) to account for pick bias.  
# - Compare results with whole-path average velocity for consistency.
# 

# In[ ]:




