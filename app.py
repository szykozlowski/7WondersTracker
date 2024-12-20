import streamlit as st
import pandas as pd
import altair as alt
import json
import time
import webbrowser
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from google.oauth2 import service_account

# dec index
def get_prev_game():
    if st.session_state["gameIndex"] > 0:
        st.session_state["gameIndex"] -= 1

# inc indexx
def get_next_game():
    if st.session_state["gameIndex"] < st.session_state["gameCount"] - 1:
        st.session_state["gameIndex"] += 1

# dictionary deep copy
def deep_copy(original):
    # base case
    if not isinstance(original, dict):
        return original
    
    # recurse
    copy = {}
    for key, value in original.items():
        if isinstance(value, dict):
            copy[key] = deep_copy(value)
        elif isinstance(value, list):
            copy[key] = [deep_copy(item) if isinstance(item, dict) else item for item in value]
        else:
            copy[key] = value
    return copy

# calculate mean score in game
def calculate_mean(game):
    total = 0
    players = 0
    for player in game["Players"]:
        total += float(player["Score"])
        players += 1

    return total / players

# calculate average values for player stats
def calculate_avgs(stats):
    for p in stats:
        # player avg stats
        player = stats[p]
        player["Average Points"] = round(player["Total Points"] / player["Games"], 2)
        player["Average Delta"] = round(player["Average Delta"] / player["Games"], 2)

    return stats

# calculate leaderboard statistics
def calculate_stats():
    # lists
    data = st.session_state["data"]
    player_stats = {}
    player_comps = {}
    delta_stats = {}
    delta_comps = {}

    # loop games
    for i, game in enumerate(data["Games"]):
        # delta data: save data omitting last game
        if i == st.session_state["gameCount"] - 1:
            delta_stats = deep_copy(player_stats)
            delta_comps = deep_copy(player_comps)

        # calculate mean
        mean = calculate_mean(game)

        # loop
        winscore = 0
        for player in game["Players"]:
            # player stats
            if player["Name"] not in player_stats:
                player_stats[player["Name"]] = {
                    "Wins":0,"Average Points":0,"Average Delta":0,
                    "Highscore":0,"Games":0,"Total Points":0}
            
            # comp stats: new player
            if player["Name"] not in player_comps:
                player_comps[player["Name"]] = {
                    player["City"]: {
                        "Wins":0,"Games":0,"Points":0,"Total Delta":0,"Wonders":0,"Gold":0,
                        "War":0,"Blue":0,"Yellow":0,"Green":0,"Purple":0}}

            # comp stats: new city
            elif player["City"] not in player_comps[player["Name"]]:
                player_comps[player["Name"]][player["City"]] = {
                        "Wins":0,"Games":0,"Points":0,"Total Delta":0,"Wonders":0,"Gold":0,
                        "War":0,"Blue":0,"Yellow":0,"Green":0,"Purple":0}

            # player stats
            stats = player_stats[player["Name"]]
            stats["Games"] += 1
            stats["Total Points"] += float(player["Score"])
            stats["Average Delta"] += float(player["Score"] - mean)
            if player["Score"] > stats["Highscore"]: stats["Highscore"] = player["Score"]
            
            # comp stats
            player_comps[player["Name"]][player["City"]]["Points"] += player["Score"]
            player_comps[player["Name"]][player["City"]]["Games"] += 1
            player_comps[player["Name"]][player["City"]]["Total Delta"] += float(player["Score"] - mean)

            # comp breakdown stats
            for category in player["Breakdown"]:
                player_comps[player["Name"]][player["City"]][category] += player["Breakdown"][category]
                
            # win stats
            if not winscore or winscore == player["Score"]:
                winscore = player["Score"]
                stats["Wins"] += 1
                player_comps[player["Name"]][player["City"]]["Wins"] += 1

    # calculate averages
    player_stats = calculate_avgs(player_stats)
    delta_stats = calculate_avgs(delta_stats)

    return player_stats, player_comps, delta_stats, delta_comps

# update essential session vars
def update_vars():
    # get data and sort
    with open("games.json", "r") as file:
        data = json.load(file)
        for game in data["Games"]:
            game["Players"] = sorted(game["Players"], key=lambda player: player["Score"], reverse=True)
        st.session_state["data"] = data

    # initial vars
    if "gameIndex" not in st.session_state: 
        count = len(data["Games"])
        st.session_state["gameIndex"] = count - 1
        st.session_state["gameCount"] = count

# statistics page
def stats_page():
    # page config
    st.header("Statistics")
    tab1, tab2 = st.tabs(["Leaderboard", "Games"])
    update_vars()

    # tabs
    with tab1:
        # leaderboard
        stats, comps, _, _ = calculate_stats()
        df = pd.DataFrame(stats).T
        st.dataframe(df.sort_values(by="Wins", ascending=False), use_container_width=True, height=len(df)*39)

    with tab2:
        # seek buttons
        c1, c2, c3 = st.columns(3)
        with c1:
            st.button("Previous", on_click=get_prev_game, use_container_width=True)
        with c2:
            st.button(f"Game Number: {st.session_state["gameIndex"] + 1}/{st.session_state["gameCount"]}", disabled=True, use_container_width=True)
        with c3:
            st.button("Next", on_click=get_next_game, use_container_width=True)

        # game data
        df = pd.DataFrame(st.session_state["data"]["Games"][st.session_state["gameIndex"]]["Players"])
        breakdown_df = df["Breakdown"].apply(pd.Series)
        df = pd.concat([df.drop(columns=["Breakdown"]), breakdown_df], axis=1)
        st.dataframe(df, hide_index=True, use_container_width=True)

    st.divider()

# get match history
def get_history():
    scores = {}
    places = {}

    # loop
    for game in st.session_state["data"]["Games"]:
        # vars
        winscore = 0
        place = 1

        # loop
        for player in game["Players"]:
            if player["Name"] not in scores: 
                scores[player["Name"]] = [player["Score"]]
                places[player["Name"]] = []

            else: scores[player["Name"]].append(player["Score"])

            # winner
            if not winscore:
                winscore = player["Score"]
                places[player["Name"]].append(place)
            
            # tie for win
            elif player["Score"] == winscore: places[player["Name"]].append(place)
            
            # else
            else:
                place += 1
                places[player["Name"]].append(place)
                

    return scores, places

# plot match history graph
def plot_history(stats, scores, places):
    # data
    data = pd.DataFrame({
        "Index": range(1, stats["Games"] + 1),
        "Score": scores,
        "Place": places
    })

    # score line and points
    score_line = (alt.Chart(data).mark_line(color="lightblue")
        .encode(
            x=alt.X("Index", title="Game", axis=alt.Axis(format="d")),
            y=alt.Y("Score", title="Score", scale=alt.Scale(domain=[min(scores) - 5, max(scores) + 5]), axis=alt.Axis(format="d", labelColor="lightblue")),
        )
    )
    score_points = (alt.Chart(data).mark_point(filled=True, size=50, color="lightblue", opacity=1)
        .encode(
            x=alt.X("Index", title="Game", axis=alt.Axis(format="d")),
            y=alt.Y("Score", title="Score", scale=alt.Scale(domain=[min(scores) - 5, max(scores) + 5]), axis=alt.Axis(format="d", labelColor="lightblue")),
        )
    )

    # place line and points
    place_line = (
        alt.Chart(data)
        .mark_line(color="yellow")
        .encode(
            x=alt.X("Index", title="Game", axis=alt.Axis(format="d")),
            y=alt.Y("Place", title="Place", scale=alt.Scale(reverse=True, domain=[1, max(places) + 1]), axis=alt.Axis(format="d", labelColor="yellow")),
        )
    )
    place_points = (alt.Chart(data).mark_point(filled=True, size=50, color="yellow", opacity=1)
        .encode(
            x=alt.X("Index", title="Game", axis=alt.Axis(format="d")),
            y=alt.Y("Place", title="Place", scale=alt.Scale(reverse=True, domain=[1, max(places) + 1]), axis=alt.Axis(format="d", labelColor="yellow")),
        )
    )

    # plot
    chart = alt.layer(score_line + score_points, place_line + place_points).resolve_scale(y="independent")
    st.altair_chart(chart, use_container_width=True)

# get synergy
def find_synergy(comp):
    categories = ["Wonders", "Gold", "War", "Blue", "Yellow", "Green", "Purple"]

    # find the category with the highest point value
    highest_category = max(categories, key=lambda category: comp[category])
    return highest_category

# analyzes comp data for best comp
def read_comps(comps):
    # vars
    max_wins = 0
    avg_pts = 0
    best = "?"
    
    # loop
    for comp in comps:
        if comp == "?": continue
        if comps[comp]["Wins"] > max_wins:
            best = comp
            avg_pts = round(float(comps[comp]["Points"])/comps[comp]["Games"], 2)

        elif comps[comp]["Wins"] == max_wins:
            temp = round(float(comps[comp]["Points"])/comps[comp]["Games"], 2)
            if temp > avg_pts:
                best = comp
                avg_pts = temp
            
    return best

# return distribution of synergy points
def get_distribution(name, comps):
    distribution = {"Wonders":0,"Gold":0,"War":0,"Blue":0,"Yellow":0,"Green":0,"Purple":0}
    points = 0
    for i, comp in enumerate(comps[name]):
        points += comps[name][comp]["Points"]
        for key in distribution:
            distribution[key] += comps[name][comp][key]
            if i == len(comps[name]) - 1:
                distribution[key] = round(100 * float(distribution[key])/points)

    return distribution

# people page
def chart_page():
    # get data
    update_vars()
    stats, comps, delta_stats, delta_comps = calculate_stats()
    scores, places = get_history()

    # player select
    st.header("Overview")
    name = st.selectbox(label="Select Player:", label_visibility="collapsed", options=stats.keys())
    
    # metric columns: value - old (delta) value
    c1, c2, c3, c4 = st.columns(4)

    # c1: wins
    delta = stats[name]["Wins"] - delta_stats[name]["Wins"]
    c1.metric("Wins", stats[name]["Wins"], delta if delta else None)
    
    # c2: win rate
    win_rate = round(100 * stats[name]["Wins"] / stats[name]["Games"], 2)
    delta_win_rate = round(100 * delta_stats[name]["Wins"] / delta_stats[name]["Games"], 2)
    delta = round(win_rate - delta_win_rate, 2)
    c2.metric("Win Rate", str(win_rate) + "%", str(delta) + "%" if delta else None)
    
    # c3, c4: avg points and delta
    delta = round(stats[name]["Average Points"] - delta_stats[name]["Average Points"], 2)
    c3.metric("Average Points", stats[name]["Average Points"], delta if delta else None)
    delta = round(stats[name]["Average Delta"] - delta_stats[name]["Average Delta"], 2)
    c4.metric("Average Delta", stats[name]["Average Delta"], delta if delta else None)

    # match history
    st.divider()
    st.header("Match History")
    plot_history(stats[name], scores[name], places[name])

    st.divider()

    # c5, c6: best/favorite
    best = read_comps(comps[name])
    syn = find_synergy(comps[name][best])
    c5, c6 = st.columns(2)
    c5.metric("Most Successful Comp", best)
    c6.metric("Synergy", syn)

    # c7, c8, c9, c10: win rates and avg points
    c7, c8, c9, c10 = st.columns(4)
    games = comps[name][best]["Games"]
    c7.metric("Win Rate", str(round(100 * float(comps[name][best]["Wins"])/games, 2)) + "%")
    c8.metric("Average Points", round(float(comps[name][best]["Points"])/games, 2))
    c9.metric("Average Delta", round(float(comps[name][best]["Total Delta"])/games, 2))
    c10.metric("Average Synergy Points", round(float(comps[name][best][syn])/games, 2))
    
    st.divider()

    # get synergy distribution
    distribution = get_distribution(name, comps)
    delta_distribution = get_distribution(name, delta_comps)

    # synergy distribution
    cols = st.columns(7)
    categories = ["Wonders", "Gold", "War", "Blue", "Yellow", "Green", "Purple"]
    for i, cat in enumerate(categories):
        delta = round(delta_distribution[cat] - distribution[cat], 1)
        cols[i].metric(cat, str(distribution[cat]) + "%", str(delta) + "%" if delta else None)

# plot pie chart visualizing synergies
def plot_synergies(breakdown, points):
    print(breakdown)
    normalized = {category: (value / points) * 100 for category, value in breakdown.items()}
    data = pd.DataFrame(list(normalized.items()), columns=["Category", "Points"])

    # color map
    color_mapping = {
        "Wonders": "#d3d3d3",  # light grey for Wonders
        "Gold": "#d4af37",  # soft gold
        "War": "#cc4d44",  # muted red
        "Blue": "#4169E1",  # pastel blue
        "Yellow": "#f2d44b",  # soft yellow
        "Green": "#228B22",  # soft green
        "Purple": "#800080"}  # muted purple
    
    # create pie chart
    chart = alt.Chart(data).mark_arc().encode(
        theta=alt.Theta(field="Points", type="quantitative", stack=True),
        color=alt.Color(field="Category", type="nominal", scale=alt.Scale(domain=list(color_mapping.keys()), range=list(color_mapping.values()))),
        tooltip=["Category", "Points"]
    ).properties(title=f"Percentage of Average Score")
    
    # Display the chart in Streamlit
    st.altair_chart(chart, use_container_width=True)

# consolidates comp data and calculates average delta
def process_comps(comps):
    maps = {}
    for player in comps:
        for comp in comps[player]:
            if comp not in maps:
                maps[comp] = {"Wins":0,"Games":0,"Points":0,"Total Delta":0,"Wonders":0,"Gold":0,
                                "War":0,"Blue":0,"Yellow":0,"Green":0,"Purple":0}
            for feature in comps[player][comp]:
                maps[comp][feature] += comps[player][comp][feature]
    
    for comp in maps:
        maps[comp]["Average Delta"] = round(maps[comp]["Total Delta"]/maps[comp]["Games"], 2)

    return maps

# produces tier list params
def get_tier_params(maps):
    tiers = []
    for comp in maps:
        if comp != "?":
            tiers.append((comp, maps[comp]["Average Delta"]))

    low = min(tiers, key=lambda x: x[1])
    high = max(tiers, key=lambda x: x[1])

    return low[1], high[1]

def tier_function(low, high, value):
    normalized = 100* (value + abs(low)) / (high + abs(low))
    if normalized > 80: return "S", normalized
    elif normalized > 50: return "A", normalized
    else: return "B", normalized

# composition page
def comp_page():
    # page config
    st.header("Compositions")
    cities = ["Alexandria", "Babylon", "Ephesus", "Giza", "Halicarnassus", "Olympia", "Rhodes"]
    tabs = st.tabs(cities)
    update_vars()

    # process data
    _, comps, _, delta_comps = calculate_stats()
    maps = process_comps(comps)
    delta_maps = process_comps(delta_comps)

    # tabs
    for i, city, in enumerate(cities):
        with tabs[i]:
            breakdown = {"Wonders":0,"Gold":0,"War":0,"Blue":0,"Yellow":0,"Green":0,"Purple":0}
            points = 0
            times = ["Day", "Night"]

            # day and night
            for j in range(2):
                st.subheader(f"{times[j]} Statistics")
                c1, c2, c3 = st.columns(3)
                mode = f"{city} {times[j]}"
                if mode not in maps:
                    st.info(f"No data for {mode}")
                    continue

                # tier
                low, high = get_tier_params(maps)
                tier, power = tier_function(low, high, maps[mode]["Average Delta"])
                powerbar = st.progress(0, text=f"Tier: {tier}")
                for val in range(int(power)):
                    time.sleep(0.01)
                    powerbar.progress(val, text=f"Tier: {tier}")

                # win rate and delta
                games = maps[mode]["Games"]
                win_rate = round(100 * float(maps[mode]["Wins"])/games, 2)
                if mode in delta_maps: delta = round(win_rate - (100 * float(delta_maps[mode]["Wins"])/games), 2)
                else: delta = None
                c1.metric("Win Rate", str(win_rate) + "%", delta if delta else None)

                # average points and delta
                average_points = round(float(maps[mode]["Points"])/games, 2)
                if mode in delta_maps: delta = round(average_points - float(delta_maps[mode]["Points"])/games, 2)
                else: delta = None
                c2.metric("Average Points", average_points, delta if delta else None)

                # average delta and delta
                average_delta = maps[mode]["Average Delta"]
                if mode in delta_maps: delta = round(average_delta - delta_maps[mode]["Average Delta"], 2)
                else: delta = None
                c3.metric("Average Delta", average_delta, delta if delta else None)
            
                for key in breakdown: breakdown[key] += maps[mode][key]
                points += maps[mode]["Points"]

                st.divider()

            # synergies
            st.subheader("Synergy Distribution")
            plot_synergies(breakdown, points)
            
# submit new entry
def add_entry():
    breakdown_cols = ["Wonders", "Gold", "War", "Blue", "Yellow", "Green", "Purple"]
    new_list = []
    for player in st.session_state["new"]:
        breakdown_dict = {key: player[key] for key in breakdown_cols}
        new_list.append({"Name":player["Name"],
                            "Score":player["Score"],
                            "City":player["City"],
                            "Breakdown": breakdown_dict})

    new_entry = {"Number":st.session_state["gameCount"],"Players":new_list}
    st.session_state["data"]["Games"].append(new_entry)
    st.session_state["gameIndex"] = st.session_state["gameCount"]
    st.session_state["gameCount"] += 1

    with open("games.json", "w") as f:
        json.dump(st.session_state["data"], f, indent=4)

    st.info("Success!")

# submit saved changes
def submit_edit():
    # convert flattened editor back into nested JSON
    edited = pd.DataFrame(st.session_state["edited"]).to_dict(orient="records")
    breakdown_cols = ["Wonders", "Gold", "War", "Blue", "Yellow", "Green", "Purple"]
    for player in edited:
        breakdown_dict = {}
        for col in breakdown_cols:
            breakdown_dict[col] = player[col]
            del(player[col])

        player["Breakdown"] = breakdown_dict

    st.session_state["data"]["Games"][st.session_state["gameIndex"]]["Players"] = edited

    with open("games.json", "w") as f:
        json.dump(st.session_state["data"], f, indent=4)

    st.info("Success!")

# confirm delete
@st.dialog("Are you sure?")
def delete():
    st.write(f"This will erase data for Game {st.session_state["gameIndex"] + 1}. This action cannot be undone.")
    if st.button("Confirm"):
        for i in range(st.session_state["gameCount"] - 1, 0, -1):
            if i == st.session_state["gameIndex"]:
                del(st.session_state["data"]["Games"][i])
                break
            else:
                st.session_state["data"]["Games"][i]["Number"] -= 1

        st.session_state["gameCount"] -= 1
        if st.session_state["gameIndex"] > 0: st.session_state["gameIndex"] -= 1

        with open("games.json", "w") as f:
            json.dump(st.session_state["data"], f, indent=4)

        st.rerun()

# submit rename
def rename():
    if st.session_state["new_name"] and st.session_state["new_name"] not in st.session_state["playerList"]:
        for game in st.session_state["data"]["Games"]:
            for player in game["Players"]:
                if player["Name"] == st.session_state["old_name"]:
                    player["Name"] = st.session_state["new_name"]

        with open("games.json", "w") as f:
            json.dump(st.session_state["data"], f, indent=4)
        
        st.info("Success!")

def upload_sheet():

    SHEET_ID = st.session_state["sheet_name"]
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


    creds = None
    credentials_dict = st.secrets["credentials"]
    credentials_dict = dict(credentials_dict)

    temp_credentials = {
        "installed": {
            "client_id": credentials_dict["client_id"],
            "project_id": credentials_dict["project_id"],
            "auth_uri": credentials_dict["auth_uri"],
            "token_uri": credentials_dict["token_uri"],
            "auth_provider_x509_cert_url": credentials_dict["auth_provider_x509_cert_url"],
            "client_secret": credentials_dict["client_secret"],
            "redirect_uris": credentials_dict.get("redirect_uris", "").splitlines(),
        }
    }

    credentials_json = json.dumps(temp_credentials)

    temp_cred_file = "temp_credentials.json"
    with open(temp_cred_file, "w") as f:
        f.write(credentials_json)


    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:

            credentials = st.secrets["credentials2"]

            credentials_dict = dict(credentials)

            temp_credentials_path = "temp_credentials.json"
            with open(temp_credentials_path, "w") as f:
                json.dump(credentials_dict, f)

            credentials = service_account.Credentials.from_service_account_file(temp_credentials_path, scopes=SCOPES)
    
    try:
        service = build("sheets", "v4", credentials=credentials)
        sheet = service.spreadsheets()

        spreadsheet = service.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
        sheets = spreadsheet.get("sheets", [])
        sheet_names = [sheet["properties"]["title"] for sheet in sheets]

        Games = []

        game_num = 0
        for name in sheet_names[1::]:
            SAMPLE_RANGE_NAME = name + "!A2:K8"
            result = (
            sheet.values()
            .get(spreadsheetId=SHEET_ID, range=SAMPLE_RANGE_NAME)
            .execute()
        )
            players = []
            game_num += 1
            for player in result['values']:
                breakdown = {
                        "Wonders": int(player[3]),
                        "Gold": int(player[4]),
                        "War": int(player[5]),
                        "Blue": int(player[6]),
                        "Yellow": int(player[7]),
                        "Green": int(player[8]),
                        "Purple": int(player[9])
                    }
                players.append({"Name":player[0],"Score":int(player[10]),"City":player[1] + " " + player[2],"Breakdown":breakdown})

            Games.append({"Number": game_num, "Players": players})
            

        final_games = {"Games":Games}
        with open("games.json", "w") as f:
            json.dump(final_games, f, indent=4)

        st.session_state["gameCount"] = game_num
        st.session_state["gameIndex"] = game_num - 1
        
    except HttpError as err:
        print(err)

# download CSV file
@st.dialog("Export Data")
def download():
    # produce leaderboard.csv
    stats, comps, _, _ = calculate_stats()
    df = pd.DataFrame(stats).T.sort_values(by="Wins", ascending=False)
    csv_file = df.to_csv().encode("utf-8")
    st.download_button(label="Download Leaderboard", data=csv_file, file_name="leaderboard.csv", use_container_width=True)
    
    # produce games.json
    json_file = json.dumps(st.session_state["data"])
    st.download_button(label="Download Game Data", data=json_file, file_name="games.json", use_container_width=True)

# data management page
def manage_data():
    st.header("Data Management")
    update_vars()

    # add new game
    with st.expander("Add New Game"):
        st.write(f"Game Number: {st.session_state["gameCount"] + 1}")

        # get player count and make table
        num = st.number_input("Players:", value=1, min_value=1, max_value=10)
        player_data = []
        for i in range(num):
            player_data.append({
                    "Name":f"Player {i + 1}",
                    "City": "?",
                    "Wonders":0,
                    "Gold":0,
                    "War":0,
                    "Blue":0,
                    "Yellow":0,
                    "Green":0,
                    "Purple":0,"Score":0})

        # store table edits
        new_entry = {"Number":st.session_state["gameCount"] + 1, "Players":player_data}
        st.session_state["new"] = st.data_editor(new_entry["Players"], key="entry_add", hide_index=True, use_container_width=True)

        # submit
        st.button("Submit Entry", on_click=add_entry, use_container_width=True)

    with st.expander("Edit Game"):
        # seek
        c1, c2, c3 = st.columns(3)
        with c1:
            st.button("Previous", on_click=get_prev_game, use_container_width=True)
        with c2:
            st.button(f"Game Number: {st.session_state["gameIndex"] + 1}/{st.session_state["gameCount"]}", disabled=True, use_container_width=True)
        with c3:
            st.button("Next", on_click=get_next_game, use_container_width=True)

        # data editor
        edit = pd.DataFrame(st.session_state["data"]["Games"][st.session_state["gameIndex"]]["Players"])
        breakdown_df = edit["Breakdown"].apply(pd.Series)
        edit = pd.concat([edit.drop(columns=["Breakdown"]), breakdown_df], axis=1)
        st.session_state["edited"] = st.data_editor(edit, key="entry_edit", hide_index=True, use_container_width=True)

        # buttons
        st.button("Submit Edit", on_click=submit_edit, use_container_width=True)
        st.button("Delete Game", on_click=delete, use_container_width=True)

    with st.expander("Rename Player"):
        # get player list
        playerList = []
        for game in st.session_state["data"]["Games"]:
            for player in game["Players"]:
                if player["Name"] not in playerList: playerList.append(player["Name"])
        st.session_state["playerList"] = playerList

        # name select
        c1, c2 = st.columns(2)
        with c1:
            st.session_state["old_name"] = st.selectbox(label="Select player:", options=playerList)
        with c2:
            st.session_state["new_name"] = st.text_input(label="New name:")

        # submit
        st.button("Submit", on_click=rename, use_container_width=True)

    # data download
    st.button("Export Data", on_click=download, use_container_width=True)

    with st.expander("Upload Game From Google Sheets"):


        # name select

        st.session_state["sheet_name"] = st.text_input(label="Sheet ID:")

        # submit
        st.button("Submit Sheet", on_click=upload_sheet, use_container_width=True)


    # data upload
    uploaded = st.file_uploader(label="Upload Game Data", type="json", accept_multiple_files=False)
    if uploaded is not None:
        try:
            # test new data
            data = json.load(uploaded)
            st.session_state["data"] = data
            test = calculate_stats()

            # write to file
            with open("games.json", "w") as f:
                json.dump(data, f, indent=4)

            # update vars
            count = len(data["Games"])
            st.session_state["gameIndex"] = count - 1
            st.session_state["gameCount"] = count

        except:
            # bad input
            st.info("Error with input file")

# main
st.set_page_config(page_title="7 Wonders Tracker", layout="centered")
with st.sidebar: st.write("7 Wonders Tracker")

#try:
pg = st.navigation([st.Page(stats_page, title="Statistics"),
                    st.Page(chart_page, title="Player Charts"),
                    st.Page(comp_page, title="Compositions"),
                    st.Page(manage_data, title="Manage Data")])
pg.run()   

#except:
    #st.info("Oh no! An error occured!")