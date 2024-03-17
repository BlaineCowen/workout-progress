import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import altair as alt
import plotly.express as px
import os
from dotenv import load_dotenv


@st.cache_data
def get_data():

    try:
        with open(".env") as f:
            load_dotenv(".env")
    except FileNotFoundError:
        load_dotenv()
        print("No .env file found")

    client_email = os.getenv("CLIENT_EMAIL")
    client_id = os.getenv("CLIENT_ID")
    private_key = os.getenv("PRIVATE_KEY").replace("\\n", "\n")
    private_key_id = os.getenv("PRIVATE_KEY_ID")

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

    # add a one rep max column
    df["one_rep_max"] = df["weight"].astype(float) / (
        1.0278 - (df["reps"].astype(float) * 0.0278)
    )

    df["one_rep_max"] = df["one_rep_max"].astype(float).round(2)

    # change date to just the date not time
    df["date"] = pd.to_datetime(df["date"]).dt.date

    # if count of exercise-name is less than 10, remove it
    df = df.groupby("exercise-name").filter(lambda x: len(x) > 20)

    return df


def main():

    st.title("Blaine Workout Progress Tracker")
    st.subheader("Updated after every workout")

    def format_func(option):
        option = option.replace("_", " ").title()
        return option

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
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d")

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
            measurement_filter: measurement_filter.replace("_", " ").title() + " (lbs)",
        },
    )
    st.plotly_chart(fig)

    workout_select = st.selectbox(
        "Select Workout",
        df["exercise-name"].sort_values().unique(),
        format_func=format_func,
        index=0,
    )

    st.plotly_chart(
        px.line(
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
    )

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

    st.altair_chart(chart)

    chart_df = df[["date", "exercise-name", "weight", "reps", "one_rep_max"]]
    st.write(chart_df)


if __name__ == "__main__":
    main()
