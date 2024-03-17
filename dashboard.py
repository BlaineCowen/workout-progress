import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import plotly.express as px


@st.cache_data
def get_data():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    credentials = ServiceAccountCredentials.from_json_keyfile_name(
        "client_key.json", scope
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

    df = get_data()

    # make one line chart with 3 lines for each workout

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

    # for workout in enumerate(workouts):
    #     workout_data = (
    #         df[df["exercise-name"] == workout[1]]
    #         .groupby("date")[measurement_filter]
    #         .max()
    #         .reset_index()
    #     )

    #     # create line chart
    #     fig = px.line(
    #         workout_data,
    #         x="date",
    #         y=measurement_filter,
    #         title=workout[1],
    #         labels={
    #             "date": "Date",
    #             measurement_filter: measurement_filter.replace("_", " ").title()
    #             + " (lbs)",
    #         },
    #     )

    #     st.plotly_chart(fig)

    workout_select = st.selectbox(
        "Select Workout",
        df["exercise-name"].sort_values().unique(),
        format_func=format_func,
        index=0,
    )

    st.plotly_chart(
        px.line(
            df[df["exercise-name"] == workout_select],
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

    st.write(df)


if __name__ == "__main__":
    main()
