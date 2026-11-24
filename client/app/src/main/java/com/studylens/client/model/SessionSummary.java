package com.studylens.client.model;

import com.google.gson.annotations.SerializedName;

/** 진행 중인 공부 세션 요약. */
public class SessionSummary {
    public long id;

    @SerializedName("start_time")
    public String startTime;

    @SerializedName("elapsed_seconds")
    public int elapsedSeconds;

    @SerializedName("distracted_seconds")
    public int distractedSeconds;

    @SerializedName("focus_seconds")
    public int focusSeconds;

    @SerializedName("focus_rate")
    public Double focusRate;

    @SerializedName("is_distracted")
    public boolean isDistracted;
}
