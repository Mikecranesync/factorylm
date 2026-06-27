package com.grash.configuration;

import java.util.Arrays;

public final class CorsOriginResolver {

    private CorsOriginResolver() {
    }

    public static String[] resolve(String frontendUrl, String configuredOrigins) {
        String source = configuredOrigins == null || configuredOrigins.trim().isEmpty()
                ? frontendUrl
                : configuredOrigins;

        if (source == null || source.trim().isEmpty()) {
            return new String[0];
        }

        return Arrays.stream(source.split(","))
                .map(String::trim)
                .filter(origin -> !origin.isEmpty())
                .distinct()
                .toArray(String[]::new);
    }
}
