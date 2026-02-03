package com.grash.utils;

import com.grash.model.AssetDowntime;

import java.util.Comparator;

public class DowntimeComparator implements Comparator<AssetDowntime> {
    @Override
    public int compare(AssetDowntime o1, AssetDowntime o2) {
        return o1.getStartsOn().compareTo(o2.getStartsOn());
    }
}
