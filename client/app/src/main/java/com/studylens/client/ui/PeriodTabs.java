package com.studylens.client.ui;

import android.app.Activity;
import android.graphics.Color;
import android.widget.TextView;

import com.studylens.client.R;

/** 랭킹 기간 탭 (오늘 / 최근 7일 / 이번 달). view_period_tabs.xml 과 함께 사용. */
public class PeriodTabs {

    public interface Listener {
        void onPeriodSelected(String period);
    }

    private final TextView[] tabs;
    private final String[] periods = {"today", "week", "month"};
    private String selected = "week";

    public PeriodTabs(Activity activity, Listener listener) {
        tabs = new TextView[]{
                activity.findViewById(R.id.tabToday),
                activity.findViewById(R.id.tabWeek),
                activity.findViewById(R.id.tabMonth),
        };
        for (int i = 0; i < tabs.length; i++) {
            final String period = periods[i];
            tabs[i].setOnClickListener(v -> {
                if (period.equals(selected)) return;
                select(period);
                listener.onPeriodSelected(period);
            });
        }
        select(selected);
    }

    public String getSelected() {
        return selected;
    }

    private void select(String period) {
        selected = period;
        for (int i = 0; i < tabs.length; i++) {
            boolean on = periods[i].equals(period);
            tabs[i].setBackgroundResource(on ? R.drawable.bg_tab_selected : R.drawable.bg_tab);
            tabs[i].setTextColor(on ? Color.WHITE : Color.parseColor("#4B5563"));
        }
    }
}
