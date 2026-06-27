package com.grash.configuration;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;

class CorsOriginResolverTest {

    @Test
    void resolveUsesFrontendUrlWhenNoOverrideIsConfigured() {
        assertArrayEquals(
                new String[]{"https://cmms.factorylm.com"},
                CorsOriginResolver.resolve("https://cmms.factorylm.com", "")
        );
    }

    @Test
    void resolveSupportsMultipleFallbackOrigins() {
        assertArrayEquals(
                new String[]{"http://localhost:3003", "https://cmms.factorylm.com"},
                CorsOriginResolver.resolve("http://localhost:3003,https://cmms.factorylm.com", "")
        );
    }

    @Test
    void resolveTrimsAndDropsBlankOverrideEntries() {
        assertArrayEquals(
                new String[]{"https://app.factorylm.com", "https://cmms.factorylm.com"},
                CorsOriginResolver.resolve(
                        "https://ignored.example",
                        " https://app.factorylm.com, ,https://cmms.factorylm.com "
                )
        );
    }
}
