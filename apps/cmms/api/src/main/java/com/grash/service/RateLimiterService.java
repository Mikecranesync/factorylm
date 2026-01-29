package com.grash.service;

import io.github.bucket4j.Bandwidth;
import io.github.bucket4j.Bucket;
import io.github.bucket4j.Refill;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

@Component
public class RateLimiterService {

    private final ConcurrentMap<String, Bucket> cache = new ConcurrentHashMap<>();

    public Bucket resolveBucket(String key) {
        return cache.computeIfAbsent(key, this::newBucket);
    }

    private Bucket newBucket(String key) {
        // 1 request per minute
        Bandwidth onePerMinute = Bandwidth.classic(1, Refill.greedy(1, Duration.ofMinutes(1)));

        // 2 requests per 5 hours
        Bandwidth twoPer5Hours = Bandwidth.classic(2, Refill.greedy(2, Duration.ofHours(5)));

        return Bucket.builder()
                .addLimit(onePerMinute)
                .addLimit(twoPer5Hours)
                .build();
    }
}
