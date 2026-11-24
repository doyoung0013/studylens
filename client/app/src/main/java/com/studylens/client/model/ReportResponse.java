package com.studylens.client.model;

import com.google.gson.annotations.SerializedName;

import java.util.List;

/** GET /api/study/report/ */
public class ReportResponse {
    public String period;
    public String start;
    public String end;
    public Totals totals;
    public Goal goal;
    public List<DailyStat> daily;
    public List<Hour> hourly;

    @SerializedName("best_hours")
    public List<BestHour> bestHours;

    @SerializedName("best_time_band")
    public Band bestTimeBand;

    @SerializedName("deep_focus")
    public DeepFocus deepFocus;

    public Frequency away;
    public Frequency phone;
    public Comparison comparison;
    public Streak streak;
    public List<String> insights;

    public static class Totals {
        @SerializedName("total_seconds") public int totalSeconds;
        @SerializedName("distracted_seconds") public int distractedSeconds;
        @SerializedName("focus_seconds") public int focusSeconds;
        @SerializedName("focus_rate") public Double focusRate;
        @SerializedName("study_days") public int studyDays;
        @SerializedName("avg_focus_seconds_per_study_day") public int avgFocusSecondsPerStudyDay;
    }

    public static class Goal {
        @SerializedName("daily_goal_minutes") public int dailyGoalMinutes;
        @SerializedName("achieved_days") public int achievedDays;
        public int days;
        @SerializedName("achievement_rate") public Double achievementRate;
    }

    public static class Hour {
        public int hour;
        @SerializedName("focus_seconds") public int focusSeconds;
    }

    public static class BestHour {
        public int hour;
        public String label;
        @SerializedName("focus_seconds") public int focusSeconds;
    }

    public static class Band {
        public String name;
        public String label;
        @SerializedName("focus_seconds") public int focusSeconds;
    }

    public static class DeepFocus {
        @SerializedName("threshold_minutes") public int thresholdMinutes;
        public int count;
        @SerializedName("total_seconds") public int totalSeconds;
        @SerializedName("longest_seconds") public int longestSeconds;
        public List<Block> blocks;
    }

    public static class Block {
        public String start;
        public String end;
        public int minutes;
    }

    public static class Frequency {
        public int count;
        @SerializedName("total_seconds") public int totalSeconds;
        @SerializedName("per_hour") public Double perHour;
    }

    public static class Comparison {
        @SerializedName("previous_focus_seconds") public int previousFocusSeconds;
        @SerializedName("change_rate") public Double changeRate;
    }

    public static class Streak {
        @SerializedName("current_days") public int currentDays;
        @SerializedName("goal_current_days") public int goalCurrentDays;
    }
}
