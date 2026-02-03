package com.grash.model.enums;

import java.util.Arrays;
import java.util.List;

public enum Priority {
    NONE(Arrays.asList("None", "Aucune")),
    LOW(Arrays.asList("Low", "Basse")),
    MEDIUM(Arrays.asList("Medium", "Moyenne")),
    HIGH(Arrays.asList("High", "Haute"));

    private final List<String> strings;

    Priority(List<String> strings) {
        this.strings = strings;
    }

    public static Priority getPriorityFromString(String string) {
        for (Priority priority : Priority.values()) {
            if (priority.strings.stream().anyMatch(str -> str.equalsIgnoreCase(string))) {
                return priority;
            }
        }
        return NONE;
    }
}
