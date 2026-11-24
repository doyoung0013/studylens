package com.studylens.client.ui;

import android.content.Context;
import android.view.LayoutInflater;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.studylens.client.R;
import com.studylens.client.model.RankingResponse;
import com.studylens.client.util.TimeFormat;

import java.util.List;

/** 랭킹 목록을 LinearLayout 컨테이너에 그린다. (친구 랭킹 / 그룹 랭킹 공용) */
public class RankingRenderer {

    public interface LongClickListener {
        void onLongClick(RankingResponse.Entry entry);
    }

    private static final String[] MEDALS = {"🥇", "🥈", "🥉"};

    public static void render(Context ctx, LinearLayout container, List<RankingResponse.Entry> entries,
                              LongClickListener longClick) {
        container.removeAllViews();
        LayoutInflater inflater = LayoutInflater.from(ctx);

        for (RankingResponse.Entry e : entries) {
            View row = inflater.inflate(R.layout.item_ranking, container, false);

            TextView rank = row.findViewById(R.id.tvRank);
            TextView name = row.findViewById(R.id.tvRankName);
            TextView sub = row.findViewById(R.id.tvRankSub);
            TextView time = row.findViewById(R.id.tvRankTime);
            View live = row.findViewById(R.id.tvLiveBadge);

            boolean hasRecord = e.totalSeconds > 0;
            rank.setText(hasRecord && e.rank <= 3 ? MEDALS[e.rank - 1] : String.valueOf(e.rank));
            name.setText(e.isMe ? e.username + " (나)" : e.username);
            time.setText(TimeFormat.minutes(e.focusSeconds));
            sub.setText(hasRecord
                    ? "전체 " + TimeFormat.minutes(e.totalSeconds) + " · 집중도 " + TimeFormat.rate(e.focusRate)
                    : "아직 기록이 없어요");
            live.setVisibility(e.studyingNow ? View.VISIBLE : View.GONE);

            if (e.isMe) row.setBackgroundResource(R.drawable.bg_row_me);
            if (longClick != null && !e.isMe) {
                row.setOnLongClickListener(v -> {
                    longClick.onLongClick(e);
                    return true;
                });
            }
            container.addView(row);
        }
    }
}
