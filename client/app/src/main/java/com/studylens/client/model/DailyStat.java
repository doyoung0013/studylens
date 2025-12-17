package com.studylens.client.model;

import com.google.gson.annotations.SerializedName;

public class DailyStat {

    @SerializedName("day")
    public int day;

    @SerializedName("total_seconds")
    public int total_seconds;
}
