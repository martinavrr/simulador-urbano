import datetime

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


def plot_commuter_status_count(model_vars_df: pd.DataFrame) -> None:
    commuter_status_df = model_vars_df.rename(
        columns=lambda x: x.replace("status_", "")
    )
    commuter_status_df["time"] = commuter_status_df["time"] / pd.Timedelta(minutes=1)
    commuter_status_df = commuter_status_df.melt(
        id_vars=["time"],
        value_vars=["stationary", "traveling"],
        var_name="traveling",
        value_name="count",
    )
    sns.relplot(
        x="time",
        y="count",
        data=commuter_status_df,
        kind="line",
        hue="status",
        aspect=1.5,
    )
    plt.gca().xaxis.set_major_formatter(
        lambda x, pos: ":".join(str(datetime.timedelta(minutes=x)).split(":")[:2])
    )
    plt.xticks(rotation=90)
    plt.title("Number of commuters by status")
