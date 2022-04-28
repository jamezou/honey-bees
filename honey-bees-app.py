# load libraries
import pandas as pd
import streamlit as st
import plotly.express as px
import researchpy as rp

# load data
df = pd.read_csv("updated_colony_data.csv")
regions = pd.read_csv("regions.csv")
test_facts_df = pd.read_csv("test_facts.csv")
seasonal_df = pd.read_csv("seasonal.csv")

# data preprocessing ------
df = df.merge(regions[["State", "Region"]], left_on="state", right_on="State")
df = df.drop("State", axis=1).sort_values(by=["year", "state"])
df.columns = df.columns.str.replace("_", " ")
df.columns = df.columns.str.lower()
df["new count"] = df["initial count"] - df["lost"]
df["end count"] = df["initial count"] - df["lost"] + df["added"] + df["renovated"]
copy_df = df.copy().sort_values(["state", "period"])  # avoid messing with original df

# linear interpolation ------
result_df = pd.DataFrame()
for state in df["state"].unique():
    st_df = df[df["state"] == state]
    miss_df = st_df.loc[:, ~st_df.columns.isin(["lost perc", "renovated perc", "new count", "end count"])]
    fill_df = miss_df.interpolate(method="linear", axis=0).ffill().bfill()
    result_df = pd.concat([result_df, fill_df])

# add back lost/renovated perc columns
linear_df = pd.merge(result_df, copy_df[["state", "period", "lost perc", "renovated perc"]],
                     on=["state", "period"], how="left")
# fill in the missing lost/renovated perc values and
linear_df["lost perc"].fillna(round(result_df["lost"] / result_df["initial count"] * 100), inplace=True)
linear_df["renovated perc"].fillna(round(result_df["renovated"] / result_df["initial count"] * 100), inplace=True)
linear_df["new count"] = result_df["initial count"] - result_df["lost"]
linear_df["end count"] = result_df["initial count"] - result_df["lost"] + result_df["added"] + result_df["renovated"]

# extra variables ------
CUSTOMLABEL = {"font_size": 14, "font_family": "Calibri"}
TRANSPARENT = 'rgba(0,0,0,0)'
STRESSORS = ["varroa mites", "other pests", "diseases", "pesticides", "other", "unknown"]
COUNTS = ["initial count", "max", "lost", "lost perc", "added", "renovated", "renovated perc", "new count", "end count"]


def stressorImpactMeasure():
    # determine which stressor has the greatest impact on bee colonies, on average
    avg_df = linear_df.groupby("state", as_index=False).agg({"varroa mites": "mean", "other pests": "mean",
                                                             "diseases": "mean", "pesticides": "mean",
                                                             "other": "mean", "unknown": "mean"})

    st.markdown(f"""<b><p style="text-align:center; font-size:26px;">Most Impactful 
                <span style="color:#ffcf20FF">Stressor</span></p></b>""", unsafe_allow_html=True)
    st.markdown(f"""<p style="text-align:center; font-size:20px;"><b>Varroa Mites</b></p>""", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([0.5, 1, 0.5])
    with col2:
        st.markdown(f"""<p style="text-align:center; font-size:18px;">Accounts for the greatest percentage of bee 
                    colonies destroyed, on average, for all states from 2015-2020</p>""", unsafe_allow_html=True)
    viewExp = st.expander("View state averages for stressors")
    with viewExp:
        st.dataframe(avg_df)


def choropleth_map(stressorChoice):
    # visualize % colonies destroyed given stressor across the country using a color scale
    fig1 = px.choropleth(linear_df,
                         locations="state code",
                         locationmode="USA-states",
                         scope="usa",
                         color=stressorChoice,
                         color_continuous_scale="Viridis_r",
                         animation_frame="period",
                         template="seaborn",
                         labels={stressorChoice: "% Destroyed"},
                         custom_data=["state", stressorChoice])
    # map appearance adjustments
    customTemp = "<br>".join(["%{customdata[0]}", "%{customdata[1]} %"])
    fig1.update_layout(title_text=f"Percentage of colonies destroyed by {stressorChoice}", title_x=0.5,
                       paper_bgcolor=TRANSPARENT,
                       geo=dict(bgcolor=TRANSPARENT))
    fig1.update_traces(hovertemplate=customTemp, hoverlabel=CUSTOMLABEL)
    # change hover text for each animation frame
    for frame in fig1.frames:
        frame.data[0].hovertemplate = customTemp
        frame.data[0].hoverlabel = CUSTOMLABEL

    return fig1


def stressorTest(grouping):
    # conduct t-test to determine if there is a difference in means
    test_df = linear_df.groupby(grouping, as_index=False).agg({"varroa mites": "mean", "other pests": "mean",
                                                        "diseases": "mean", "pesticides": "mean",
                                                        "other": "mean", "unknown": "mean"})
    test_df = test_df.sort_values(grouping)
    ans_df = test_df.copy()
    groupList = []
    if grouping == "quarter":
        groupList = ["Q1", "Q2", "Q3", "Q4"]
    elif grouping == "region":
        groupList = ["Midwest", "Northeast", "South", "West"]

    # run t-test to compare means
    for var in STRESSORS:
        for x in groupList:
            summary, results = rp.ttest(group1=linear_df[var][linear_df[grouping] == x], group1_name=x,
                                        group2=linear_df[var], group2_name="overall")
            ALPHA = 0.05
            p_value = results.iloc[3, 1]
            if p_value < ALPHA:
                ans_df[var][ans_df[grouping] == x] = "reject"
            else:
                ans_df[var][ans_df[grouping] == x] = "fail"
            # view raw test results: measures were manually inputted into another file for stressorTestMeasure
            # st.write(x, var)
            # st.write(results[0:4])
            # st.write(summary.iloc[0:2, [0, 2, 1]])

    # display compact test and result tables
    st.dataframe(test_df)
    st.dataframe(ans_df)


def stressorTestMeasure(stressorChoice):
    # corresponding to the stressorTest, display the quarterly and regional effect measures
    col1, col2, col3 = st.columns([1, 0.20, 1])  # width of text boxes
    with col1:
        st.markdown(f"""<b><p style="text-align:center; font-size:25px;">Effect Per <span style="color:#ffcf20FF"
                    >Quarter</span></p></b>""", unsafe_allow_html=True)
        st.markdown(f"""<p style="text-align:center; font-size:18px;">
                   {test_facts_df[test_facts_df["stressor"] == stressorChoice]["quarter fact"].values[0]}</p>""",
                    unsafe_allow_html=True)
    with col3:
        st.markdown(f"""<b><p style="text-align:center; font-size:26px;">Effect Per <span style="color:#ffcf20FF"
                    >Region</span></p></b>""", unsafe_allow_html=True)
        st.markdown(f"""<p style="text-align:center; font-size:18px;">
                   {test_facts_df[test_facts_df["stressor"] == stressorChoice]["region fact"].values[0]}</p>""",
                    unsafe_allow_html=True)


def stateMeasure(stressorChoice):
    # determine which state corresponds to the greatest % of colonies destroyed of given stressor
    stateHighVal = round(linear_df.groupby(["state"])[stressorChoice].mean().max(), 1)
    stateHigh = linear_df.groupby(["state"])[stressorChoice].mean().idxmax()
    stateLowVal = round(linear_df.groupby(["state"])[stressorChoice].mean().min(), 1)
    stateLow = linear_df.groupby(["state"])[stressorChoice].mean().idxmin()

    col1, col2, col3 = st.columns([0.20, 1, 0.20])
    with col2:
        st.markdown(f"""<b><p style="text-align:center; font-size:26px;">Most and Least Impacted 
                    <span style="color:#ffcf20FF">State</span></p></b>""", unsafe_allow_html=True)
        st.markdown(f"""<p style="text-align:center; font-size:18px;">{stateHigh} has the <b>highest</b> average of 
                    {stateHighVal} % of bee colonies destroyed by {stressorChoice}</p>""", unsafe_allow_html=True)
        st.markdown(f"""<p style="text-align:center; font-size:18px;">{stateLow} has the <b>lowest</b> average of 
                    {stateLowVal} % of bee colonies destroyed by {stressorChoice}</p>""", unsafe_allow_html=True)


def stressorComparison(data, stateChoice):
    # comparison of % colonies destroyed across stressors within selected state
    # can isolate each stressor by selecting in legend
    state_df = data[data["state"] == stateChoice]
    fig1 = px.line(state_df,
                   x="period",
                   y=STRESSORS,
                   labels={"value": "percentage", "variable": "stressor"},
                   color_discrete_sequence=px.colors.qualitative.T10)
    # line graph appearance adjustments
    fig1.update_layout(title_text=f"Percentage of colonies destroyed across stressors in {stateChoice}",
                       title_x=0.5, paper_bgcolor=TRANSPARENT,
                       plot_bgcolor=TRANSPARENT)
    fig1.update_xaxes(tickangle=40)
    fig1.update_traces(hoverlabel=CUSTOMLABEL)

    return fig1


def effortsGraph(data, stateChoice, timeFrameChoice):
    state_df = data[data["state"] == stateChoice]
    # sidebar user option for time range
    if timeFrameChoice == "custom range":
        start, end = st.sidebar.select_slider("Pick a time frame", list(data["period"].unique()),
                                              value=["2015Q1", "2020Q4"])
        timeMask = (state_df["period"] >= start) & (state_df["period"] <= end)
        state_df = state_df.loc[timeMask]

    # comparison of colony numbers of initial counts to end count
    fig1 = px.bar(state_df,
                  x="period",
                  y=["initial count", "end count"],
                  barmode="group",
                  labels={"value": "number of colonies", "variable": "counts"},
                  color_discrete_map={"initial count": "#714925", "end count": "#FFD220"})
    fig1.update_layout(title_text=f"Initial vs. end colony population counts in {stateChoice}", title_x=0.5,
                       paper_bgcolor=TRANSPARENT, plot_bgcolor=TRANSPARENT)
    fig1.update_xaxes(tickangle=40)
    fig1.update_traces(hoverlabel=CUSTOMLABEL)

    # general colony population change
    # new count used instead of lost to provide better comparison with initial and max
    fig2 = px.line(state_df,
                   x="period",
                   y=["max", "initial count", "new count"],
                   labels={"value": "number of colonies", "variable": "counts"},
                   color_discrete_sequence=px.colors.qualitative.T10)
    fig2.update_layout(title_text=f"Colony population change in {stateChoice}", title_x=0.5,
                       paper_bgcolor=TRANSPARENT, plot_bgcolor=TRANSPARENT)
    fig2.update_xaxes(tickangle=40)
    fig2.update_traces(hoverlabel=CUSTOMLABEL)

    return fig1, fig2


def endCountMeasure(stateChoice):
    # determine what percentage of colony populations have an end count that is higher than the initial count
    state_df = linear_df[linear_df["state"] == stateChoice][["initial count", "end count"]]
    greater_df = state_df[state_df["end count"] > state_df["initial count"]]
    perc = (len(greater_df)/len(state_df))*100

    return perc


def seasonalMeasure():
    seasonal_states_df = seasonal_df[seasonal_df["seasonal"] == "yes"]
    q13_df = seasonal_states_df[(seasonal_states_df["Q1"] == "low") & (seasonal_states_df["Q3"] == "high")]

    fig1 = px.choropleth(q13_df,
                         locations="state code",
                         locationmode="USA-states",
                         scope="usa",
                         template="seaborn",
                         custom_data=["state"],
                         color_discrete_sequence=px.colors.qualitative.Plotly_r)

    customTemp = "<br>".join(["%{customdata[0]}"])
    fig1.update_layout(title_text=f"States with low counts in Q1 and high counts in Q3", title_x=0.5,
                       paper_bgcolor=TRANSPARENT,
                       geo=dict(bgcolor=TRANSPARENT))
    fig1.update_traces(hovertemplate=customTemp, hoverlabel=CUSTOMLABEL)
    st.plotly_chart(fig1)


def customLine(locFilter, colChoice):
    # % colonies destroyed by selected stressor for selected state(s)
    customTemp = "%{customdata[0]}"
    customTitle = ""
    if colChoice in STRESSORS:
        customTitle = f"Percentage of colonies destroyed by {colChoice} across states"
        customTemp = "%{customdata[0]} %"
    elif colChoice == "initial count":
        customTitle = "Initial total count of colonies quarterly by state"
    elif colChoice == "max":
        customTitle = "Maximum amount of colonies recorded quarterly by state"
    elif colChoice == "lost":
        customTitle = "Total colonies lost quarterly by state"
    elif colChoice == "lost perc":
        customTitle = "Percentage of colonies lost from initial count quarterly by state"
        customTemp = "%{customdata[0]} %"
    elif colChoice == "added":
        customTitle = f"Total colonies added quarterly by state"
    elif colChoice == "renovated":
        customTitle = "Total colonies renovated quarterly by state"
    elif colChoice == "renovated perc":
        customTitle = "Percentage of colonies renovated quarterly by state"
        customTemp = "%{customdata[0]} %"

    if locFilter in linear_df["region"].unique():
        fig1 = px.line(linear_df[linear_df["region"] == locFilter],
                       x="period",
                       y=colChoice,
                       color="state",
                       custom_data=[colChoice])
        customTitle = customTitle[:36] + colChoice + " in the " + locFilter
    else:
        # allow column selection paired with stateChoice multiselect for user-select parameter comparisons
        fig1 = px.line(linear_df[linear_df["state"].isin(locFilter)],
                       x="period",
                       y=colChoice,
                       color="state",
                       custom_data=[colChoice])
    # custom line graph appearance adjustments
    fig1.update_layout(title_text=customTitle, title_x=0.5, paper_bgcolor=TRANSPARENT,
                       plot_bgcolor=TRANSPARENT)
    fig1.update_xaxes(tickangle=40)
    fig1.update_traces(hovertemplate=customTemp, hoverlabel=CUSTOMLABEL)

    return fig1


def main():
    # overall streamlit page styling
    st.markdown(
        """
        <style>
        span[data-baseweb="tag"] {
            background-color: #35363a;
        } 
        div[data-baseweb="select"]>div {
            border-color:rgb(194, 189, 189);
        }
        .css-ffhzg2 {
            background: #35363a;
    
        }
        ::-webkit-scrollbar {
            background: #655e59;
        }
        </style>
        """, unsafe_allow_html=True)

    # sidebar user page navigation
    st.sidebar.markdown(f"""<p style="font-size:14px;">Created by: Jame Zou</p>""", unsafe_allow_html=True)
    st.sidebar.header("Navigation")
    navChoice = st.sidebar.radio("Go to", ["What's the buzz?", "The swarm of issues", "The efforts beeing made",
                                           "More about the data"])

    if navChoice == "What's the buzz?":
        # main page
        st.markdown(f"""<h1 style="font-size:36px;"<p> What\'s the buzz with <span style="color:#ffcf20FF"
                    >honey bees</span> in the United States?</p></h1>""", unsafe_allow_html=True)
        intro = """Like all pollinators, bees are important to the environment as they promote plant growth
                   and reproduction. In particular, honey bee colonies managed by beekeepers across 
                   the United States play a crucial role in fueling the country’s food supply. Farmers and 
                   growers need honey bees to pollinate their crops to ensure better crop growth and yield."""
        issue = """However, honey bee colonies have declined over the years as <b><dfn title=
                   "phenomenon resulting in a dead colony due to the lack of adult bees, despite a live queen bee">
                   Colony Collapse Disorder (CCD)</dfn></b> poses a serious threat to their overall well-being and 
                   future. While a scientific cause has not been identified, several stressors that contribute to the 
                   downfall of colony numbers have been studied and recorded each quarter from 2015 to 2020."""
        note = """Note: Data collection was suspended in the second quarter of 2019. Six states are not 
                  involved in this dataset, including Alaska, Delaware, Nevada, New Hampshire, Rhode Island, 
                  and Wyoming."""
        st.markdown(f"""<p style="font-size:18px;">{intro}\n\n</p>""", unsafe_allow_html=True)
        st.markdown(f"""<p style="font-size:18px;">{issue}</p>""", unsafe_allow_html=True)
        st.markdown(f"""<p style="font-size:12px;">{note}</p>""", unsafe_allow_html=True)

    elif navChoice == "The swarm of issues":
        # main page
        st.markdown(f"""<h1 style="font-size:36px;"<p>The <span style="color:#ffcf20FF"
                    >swarm</span> of issues</p></h1>""", unsafe_allow_html=True)
        intro = """Honey bee populations face numerous harmful factors from pests to environmental issues. The most
                   notable ones include the following: 
                   <ul style="padding-left:40px;">
                   <li>varroa mites</li>
                   <li>other pests: tracheal mites, nosema, hive beetle, moths, etc</li>
                   <li>diseases: American and European foulbrood, chalkbrood, stonebrood, paralysis (acute and chronic),
                   kashmir, deformed wing, sacbrood, IAPV, Lake Sinai II, etc</li>
                   <li>pesticides</li>
                   <li>other: weather, starvation, insufficient forage, queen failure, hive damage/destroyed, etc</li>
                   <li>unknown: cause of colony death not specified</li>
                   </ul>"""
        st.markdown(f"""<p style="font-size:18px;">{intro}\n\n</p>""", unsafe_allow_html=True)
        stressorImpactMeasure()

        # sidebar user options
        st.sidebar.header("Options")
        stressorChoice = st.sidebar.selectbox("Select stressor", STRESSORS, index=0)
        # show graph for the most affected state for given stressor
        customIndex = {"varroa mites": 8, "other pests": 8, "diseases": 26, "pesticides": 13, "other": 35, "unknown": 43}
        stateChoice = st.sidebar.selectbox("Select state", list(linear_df["state"].unique()), index=customIndex[stressorChoice])
        st.markdown(f"""<b><p style="font-size:30px;">Damage caused by <span style="color:#ffcf20FF"
                    >{stressorChoice}</span>\n\n</p></b>""", unsafe_allow_html=True)
        st.plotly_chart(choropleth_map(stressorChoice))

        # display text
        stressorTestMeasure(stressorChoice)
        stateMeasure(stressorChoice)

        st.markdown(f"""<br><b><p style="font-size:30px;">Overall damage within <span style="color:#ffcf20FF"
                    >State</span>\n\n</p></b>""", unsafe_allow_html=True)
        line1 = stressorComparison(linear_df, stateChoice)
        st.plotly_chart(line1)

        viewExp = st.expander("View source data and test results from analysis")
        with viewExp:
            grouping = st.selectbox("Group by", ["quarter", "region"])
            stressorTest(grouping)

    elif navChoice == "The efforts beeing made":
        st.sidebar.header("Options")
        st.markdown(f"""<h1 style="font-size:36px;"<p>The efforts <span style="color:#ffcf20FF"
                    >beeing</span> made</p></h1>""", unsafe_allow_html=True)
        intro = """To combat the various threats honey bee colonies encounter, beekeepers and researchers work to 
                   revive affected colonies by adding more healthy adult bees and making the necessary renovations
                   or adding new colonies."""
        st.markdown(f"""<p style="font-size:18px;">{intro}\n\n</p>""", unsafe_allow_html=True)

        # sidebar user options
        stateChoice = st.sidebar.selectbox("Select state", list(linear_df["state"].unique()), index=18)
        view_all = st.sidebar.checkbox("View percentages for all states")
        timeFrameChoice = st.sidebar.radio("Select time frame", ["all years", "custom range"])

        gbar1, line1 = effortsGraph(linear_df, stateChoice, timeFrameChoice)
        st.plotly_chart(gbar1)
        st.markdown(f"""<p style="text-align:center; font-size:12px;">Note: end count is the initial count minus
                    the lost colonies and plus the number of added and renovated colonies</p>""",
                    unsafe_allow_html=True)
        # display text
        perc = round(endCountMeasure(stateChoice))
        st.markdown(f"""<b><p style="text-align:center; font-size:26px;">
                    <span style="color:#ffcf20FF">{perc} %</span> of colony populations are restored to 
                    numbers greater than the initial count at the end of each quarter in {stateChoice}</p></b>""",
                    unsafe_allow_html=True)

        # display all state percentages if checked
        perc_data = pd.DataFrame(columns=["state", "percentage"])
        if view_all:
            for state in list(linear_df["state"].unique()):
                perc = round(endCountMeasure(state), 2)
                perc_data.loc[len(perc_data)] = state, perc
            st.dataframe(perc_data)

        # view each state plot to observe seasonality; used to create seasonal file
        # for state in (list(df["state"].unique())):
        #     gbar1, line1 = effortsGraph(linear_df, state, timeFrameChoice)
        #     st.plotly_chart(line1)

        st.markdown("<br>", unsafe_allow_html=True)
        st.plotly_chart(line1)
        st.markdown(f"""<p style="text-align:center; font-size:12px;">Note: new count is obtained by 
                    subtracting the total colonies lost from the initial count</p>""", unsafe_allow_html=True)
        context = """Meanwhile, studying when bee colony populations are at its highest and lowest can also point to 
                     the possible seasonal effects due to weather, time of the year, or other factors. This can be
                     observed by viewing colony population change for new count with each state. Of the states
                     which show strong seasonality, the most prominent feature is the low population counts in Q1 and 
                     high counts in Q3."""

        st.markdown(f"""<br><p style="font-size:18px;">{context}\n\n</p>""", unsafe_allow_html=True)
        seasonalMeasure()

    else:
        # main page
        st.markdown(f"""<h1 style="font-size:36px;"<p>More about the <span style="color:#ffcf20FF"
                    >data</span></p></h1>""", unsafe_allow_html=True)

        st.markdown(f"""<b><p style="font-size:26px;">Compare a variable between state(s) or within region</p></b>""",
                    unsafe_allow_html=True)
        # user options
        optionExpander = st.expander("Select options")
        with optionExpander:
            locChoice = st.selectbox("Filter location by", ["state(s)", "region"])
            if locChoice == "state(s)":
                locFilter = st.multiselect("Select state(s)", list(linear_df["state"].unique()),
                                           default=["California", "Texas"])
            else:
                locFilter = st.selectbox("Select state(s)", list(linear_df["region"].unique()), index=2)
            colChoice = st.selectbox("Select variable", STRESSORS + COUNTS)

        st.plotly_chart(customLine(locFilter, colChoice))  # additional graph

        st.markdown(f"""<b><p style="font-size:26px;">Determining how to interpolate the missing values</p></b>""",
                    unsafe_allow_html=True)
        st.markdown(f"""<p style="font-size:18px;">Although less than 5% of values in the dataset were missing, there 
                    was a significant gap created by the missing data for 2019 Q2. Therefore, instead of dropping all 
                    the missing values, which in turn would also remove the period 2019 Q2 for all states, the better 
                    approach would be to interpolate the missing values. Given that this is multivariate time series 
                    data, filling in the missing values with a fixed value such as the mean or median would not be an 
                    ideal choice. As such, the route taken was linear interpolation which would generate values 
                    based on that of the nearest points. Since it would not make sense for say, Alabama's values to
                    play a part in the estimates for Arkansas, the data was grouped by state to perform linear
                    interpolation on each subset. Variables such as 'lost perc', 'renovated perc', 'new count', and
                    'end count' were updated afterward.</p><br>""", unsafe_allow_html=True)
        st.markdown(f"""<p style="font-size:18px;">The differences between the before and after interpolation 
                    can be observed in the graphs below. In particular, Hawaii had a significant amount of absent 
                    data which were filled in accordingly. </p><br>""", unsafe_allow_html=True)
        optionExpander2 = st.expander("Select options")
        with optionExpander2:
            exampleState = st.selectbox("Select state", df["state"].unique(), index=8)
            graphOption = st.selectbox("Select category of data", ["stressors", "counts"])
            viewData = st.checkbox("View raw data")

        # compare charts for before and after interpolation
        if graphOption == "stressors":
            st.plotly_chart(stressorComparison(df, exampleState))
            st.plotly_chart(stressorComparison(linear_df, exampleState))
        else:
            line1, line2 = effortsGraph(df, exampleState, timeFrameChoice="all years")
            line3, line4 = effortsGraph(linear_df, exampleState, timeFrameChoice="all years")
            st.plotly_chart(line2)
            st.plotly_chart(line4)
        if viewData:
            col1, col2, col3 = st.columns([1, 0.25, 1])
            with col1:
                st.markdown(f"""<b><p style="text-align:center; font-size:26px;">Before</p></b>""",
                            unsafe_allow_html=True)
                st.dataframe(df.sort_values(["state", "period"]))
            with col3:
                st.markdown(f"""<b><p style="text-align:center; font-size:26px;">After</p></b>""",
                            unsafe_allow_html=True)
                st.dataframe(linear_df)


if __name__ == "__main__":
    main()
