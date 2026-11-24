package com.studylens.client.model;

import com.google.gson.annotations.SerializedName;

/** GET/PATCH /api/me/goal/ */
public class GoalBody {
    @SerializedName("daily_goal_minutes")
    public int dailyGoalMinutes;

    public GoalBody(int minutes) {
        this.dailyGoalMinutes = minutes;
    }
}
