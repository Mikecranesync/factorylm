package com.grash.model.enums;

import java.util.Arrays;
import java.util.List;

public enum Status {
    OPEN(Arrays.asList("Open", "Ouvert")),
    IN_PROGRESS(Arrays.asList("IN_PROGRESS", "In Progress", "En cours")),
    ON_HOLD(Arrays.asList("ON_HOLD", "On hold", "En pause")),
    COMPLETE(Arrays.asList("Complete", "Terminé"));

    private final List<String> strings;

    Status(List<String> strings) {
        this.strings = strings;
    }

    public static Status getStatusFromString(String string) {
        for (Status status : Status.values()) {
            if (status.strings.stream().anyMatch(str -> str.equalsIgnoreCase(string))) {
                return status;
            }
        }
        return OPEN;
    }

}
