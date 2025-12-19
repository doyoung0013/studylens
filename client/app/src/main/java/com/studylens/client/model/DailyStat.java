package com.studylens.client.model;

import com.google.gson.annotations.SerializedName;

public class DailyStat {

    @SerializedName("date")
    public String date;   // "2025-12-19"

    @SerializedName("duration_seconds")
    public int durationSeconds;
}
