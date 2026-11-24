package com.studylens.client.model;

import com.google.gson.annotations.SerializedName;

/** GET /api/stats/daily/ 응답 항목 (하루 단위 통계). */
public class DailyStat {

    @SerializedName("date")
    public String date;                 // "2026-11-24"

    @SerializedName("total_seconds")
    public int totalSeconds;            // 딴짓 포함 전체 공부 시간

    @SerializedName("distracted_seconds")
    public int distractedSeconds;       // 딴짓(휴대폰) 시간

    @SerializedName("focus_seconds")
    public int focusSeconds;            // 순공부 시간 = 전체 - 딴짓

    @SerializedName("focus_rate")
    public Double focusRate;            // 집중도(%) — 기록이 없으면 null

    @SerializedName("goal_seconds")
    public int goalSeconds;             // 하루 목표 순공부 시간

    @SerializedName("goal_rate")
    public double goalRate;             // 목표 달성률(%) — 100 초과 가능

    @SerializedName("goal_achieved")
    public boolean goalAchieved;

    // 리포트(/api/study/report/)의 daily 항목에서만 채워짐
    @SerializedName("away_count")
    public int awayCount;

    @SerializedName("phone_count")
    public int phoneCount;
}
