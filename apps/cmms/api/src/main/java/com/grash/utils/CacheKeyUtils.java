package com.grash.utils;

import java.util.Date;

public class CacheKeyUtils {
    public static long roundToNearest20Minutes(Date date) {
        long millis = date.getTime();
        long interval = 20 * 60 * 1000L; // 10 minutes in ms
        return (millis / interval) * interval;
    }

    public static String dateRangeKey(Long userId, Date start, Date end) {
        return userId + "_" + roundToNearest20Minutes(start) + "_" + roundToNearest20Minutes(end);
    }
}
