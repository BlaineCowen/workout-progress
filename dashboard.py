import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import altair as alt
import plotly.express as px
import os
from dotenv import load_dotenv
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
from datetime import datetime
from google.cloud import storage


@st.cache_data
def get_data():

    # try st.secrets
    try:
        client_email = st.secrets["CLIENT_EMAIL"]
        client_id = st.secrets["CLIENT_ID"]
        private_key = st.secrets["PRIVATE_KEY"].replace("\\n", "\n")
        private_key_id = st.secrets["PRIVATE_KEY_ID"]

    except KeyError:
        print("No secrets found")

    credentials_dict = {
        "type": "service_account",
        "client_email": client_email,
        "client_id": client_id,
        "private_key": private_key,
        "private_key_id": private_key_id,
        "token_uri": "https://accounts.google.com/o/oauth2/token",
    }

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    credentials = ServiceAccountCredentials.from_json_keyfile_dict(
        credentials_dict, scope
    )

    gc = gspread.authorize(credentials)

    spreadsheet_key = "1-_NPaN7lCCnDCf-vEDEpjxQYc9DALrbbNB4Uq3-lrz8"
    book = gc.open_by_key(spreadsheet_key)
    worksheet = book.worksheet("db")  # We are using the first sheet

    # get all values in the first sheet
    table = worksheet.get_all_values()

    ## convert table data into pandas dataframe
    df = pd.DataFrame(table[1:], columns=table[0])

    # force numberic columns to be numeric
    df["weight"] = pd.to_numeric(df["weight"], errors="coerce")
    df["reps"] = pd.to_numeric(df["reps"], errors="coerce")

    # add a one rep max column
    df["one_rep_max"] = df["weight"].astype(float) / (
        1.0278 - (df["reps"].astype(float) * 0.0278)
    )

    df["one_rep_max"] = df["one_rep_max"].astype(float).round(2)

    # change date to just the date not time

    # if count of exercise-name is less than 10, remove it
    df = df.groupby("exercise-name").filter(lambda x: len(x) > 20)

    return df


def main():

    st.title("Blaine Workout Progress Tracker")
    st.subheader("Updated after every workout")

    def format_func(option):
        option = option.replace("_", " ").title()
        return option

    data_tab, input_tab = st.tabs(["Data", "Input Data"])

    with data_tab:

        measurement_filter = st.radio(
            "Select measurement",
            ["weight", "one_rep_max"],
            format_func=format_func,
            index=1,
            horizontal=True,
        )

        days = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]

        # make a chart with days of the week and month
        df = get_data()

        df["date"] = pd.to_datetime(df["date"])

        df = df[df["date"] != ""]

        df["week"] = (
            df["date"].dt.isocalendar().week.astype(str)
            + "-"
            + (df["date"].dt.isocalendar().year % 100).astype(str)
        )
        df["month"] = df["date"].dt.month_name()

        df["day_of_week"] = pd.Categorical(
            df["date"].dt.day_name(), ordered=True, categories=days
        )

        workouts = [
            "Bench Press (Barbell)",
            "Squat (Barbell)",
            "Deadlift (Barbell)",
        ]
        # make one line chart with 3 lines for each workout
        workout_data = (
            df[df["exercise-name"].isin(workouts)]
            .groupby(["date", "exercise-name"])[measurement_filter]
            .max()
            .reset_index()
        )

        fig = px.line(
            workout_data,
            x="date",
            y=measurement_filter,
            color="exercise-name",
            title="Workout Progress",
            labels={
                "date": "Date",
                measurement_filter: measurement_filter.replace("_", " ").title()
                + " (lbs)",
            },
        )
        st.plotly_chart(fig, use_container_width=True)

        workout_select = st.selectbox(
            "Select Workout",
            df["exercise-name"].sort_values().unique(),
            format_func=format_func,
            index=0,
        )

        select_chart = px.line(
            df[df["exercise-name"] == workout_select]
            .groupby(["date", "exercise-name"])[measurement_filter]
            .max()
            .reset_index(),
            x="date",
            y=measurement_filter,
            title=workout_select,
            labels={
                "date": "Date",
                measurement_filter: measurement_filter.replace("_", " ").title()
                + " (lbs)",
            },
        )

        st.plotly_chart(select_chart, use_container_width=True)

        chart = (
            alt.Chart(df, title="Workout by day")
            .mark_rect()
            .encode(
                x=alt.X("week:O", sort=alt.SortField("date")),
                y=alt.Y("day_of_week:O", sort=days),
                color=alt.Color(
                    "sum(reps):Q",
                    scale=alt.Scale(scheme="blues"),
                ),
                tooltip=[
                    alt.Tooltip("week", title="Week"),
                    alt.Tooltip("day_of_week", title="Day of Week"),
                    alt.Tooltip("sum(reps)", title="Workouts"),
                ],
            )
        )

        st.altair_chart(chart, use_container_width=True)

        chart_df = df[["date", "exercise-name", "weight", "reps", "one_rep_max"]]
        st.write(chart_df, use_container_width=True)

    with input_tab:

        def download_blob(bucket_name, source_blob_name, destination_file_name):

            try:
                client_email = st.secrets["CLIENT_EMAIL"]
                client_id = st.secrets["CLIENT_ID"]
                private_key = st.secrets["PRIVATE_KEY"].replace("\\n", "\n")
                private_key_id = st.secrets["PRIVATE_KEY_ID"]

            except KeyError:
                print("No secrets found")

            credentials_dict = {
                "type": "service_account",
                "client_email": client_email,
                "client_id": client_id,
                "private_key": private_key,
                "private_key_id": private_key_id,
                "token_uri": "https://accounts.google.com/o/oauth2/token",
            }

            storage_client = storage.Client.from_service_account_info(credentials_dict)

            bucket = storage_client.bucket(bucket_name)

            # using `Bucket.blob` is preferred here.
            blob = bucket.blob(source_blob_name)
            blob.download_to_filename(destination_file_name)

        download_blob("bcows-workout", "config.yaml", "secure-config.yaml")

        with open("secure-config.yaml") as file:
            config = yaml.load(file, Loader=SafeLoader)

        with open("secure-config.yaml", "w") as file:
            yaml.dump(config, file, default_flow_style=False)

        authenticator = stauth.Authenticate(
            config["credentials"],
            config["cookie"]["name"],
            config["cookie"]["key"],
            config["cookie"]["expiry_days"],
            config["preauthorized"],
        )

        if (
            st.session_state["authentication_status"] is False
            or st.session_state["authentication_status"] is None
        ):
            authenticator.login()

        if st.session_state["authentication_status"]:
            logout = authenticator.logout()

            if logout:
                st.rerun()

            st.subheader("Add Data")

            start_data = {
                "exercise-name": "",
                "weight": 0,
                "reps": 0,
                "orm": 0,
                "previous_orm": 0,
                "previous_maxweight": 0,
            }

            if "start_df" not in st.session_state:
                st.session_state["start_df"] = pd.DataFrame(start_data, index=[0])
                # reset the index
                st.session_state["start_df"] = st.session_state["start_df"].reset_index(
                    drop=True
                )

            def update_calcs():
                # Create the data editor
                edited_df = st.data_editor(
                    st.session_state["start_df"],
                    num_rows="dynamic",
                    column_config={
                        "exercise-name": st.column_config.SelectboxColumn(
                            width="small",
                            options=df["exercise-name"].sort_values().unique(),
                        ),
                        "weight": st.column_config.NumberColumn(),
                        "reps": st.column_config.NumberColumn(),
                    },
                    disabled={
                        "orm": True,
                        "previous_orm": True,
                        "previous_maxweight": True,
                    },
                    hide_index=True,
                )

                if not st.session_state["start_df"].equals(edited_df):

                    st.session_state["start_df"] = edited_df

                    st.session_state["start_df"]["orm"] = st.session_state["start_df"][
                        "weight"
                    ] / (1.0278 - (st.session_state["start_df"]["reps"] * 0.0278))

                    st.session_state["start_df"]["orm"] = st.session_state["start_df"][
                        "orm"
                    ].round(2)

                    st.session_state["start_df"]["previous_orm"] = df.loc[
                        df["exercise-name"]
                        == st.session_state["start_df"]["exercise-name"].values[0],
                        "one_rep_max",
                    ].max()
                    # rerun

                    st.session_state["start_df"]["previous_maxweight"] = df.loc[
                        df["exercise-name"]
                        == st.session_state["start_df"]["exercise-name"].values[0],
                        "weight",
                    ].max()

                    st.rerun()

            update_calcs()

            if st.button("Submit to db"):
                # add to db
                # get google auth
                # get google sheet
                def add_to_sheets(df):
                    try:
                        client_email = st.secrets["CLIENT_EMAIL"]
                        client_id = st.secrets["CLIENT_ID"]
                        private_key = st.secrets["PRIVATE_KEY"].replace("\\n", "\n")
                        private_key_id = st.secrets["PRIVATE_KEY_ID"]

                    except KeyError:
                        print("No secrets found")

                    credentials_dict = {
                        "type": "service_account",
                        "client_email": client_email,
                        "client_id": client_id,
                        "private_key": private_key,
                        "private_key_id": private_key_id,
                        "token_uri": "https://accounts.google.com/o/oauth2/token",
                    }

                    scope = [
                        "https://spreadsheets.google.com/feeds",
                        "https://www.googleapis.com/auth/drive",
                    ]

                    credentials = ServiceAccountCredentials.from_json_keyfile_dict(
                        credentials_dict, scope
                    )

                    gc = gspread.authorize(credentials)

                    spreadsheet_key = "1-_NPaN7lCCnDCf-vEDEpjxQYc9DALrbbNB4Uq3-lrz8"
                    book = gc.open_by_key(spreadsheet_key)
                    worksheet = book.worksheet("db")

                    for i in range(len(df)):
                        # add to db
                        worksheet.append_row(
                            [
                                datetime.now().strftime(
                                    "%Y-%m-%d %H:%M:%S"
                                ),  # Get the current timestamp in the desired format
                                st.session_state["start_df"].loc[i, "exercise-name"],
                                int(st.session_state["start_df"].loc[i, "weight"]),
                                int(st.session_state["start_df"].loc[i, "reps"]),
                                "",
                                int(st.session_state["start_df"].loc[i, "orm"]),
                            ]
                        )

                    # erase data in session
                    st.session_state["start_df"] = pd.DataFrame(start_data, index=[0])
                    edited_df = st.session_state["start_df"]

                    # clear cache and rerun
                    get_data.clear()
                    get_data()
                    st.rerun()

                add_to_sheets(st.session_state["start_df"])


if __name__ == "__main__":
    main()
