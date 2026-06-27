package com.grash.configuration;

import com.grash.security.CurrentUserResolver;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.util.List;


@Configuration
@RequiredArgsConstructor
public class WebMvcConfig implements WebMvcConfigurer {

    private static final long MAX_AGE_SECS = 3600;
    private final CurrentUserResolver currentUserResolver;
    @Value("${frontend.url}")
    private String frontendUrl;
    @Value("${security.cors.enabled}")
    private boolean enableCors;
    @Value("${security.cors.allowed-origins:}")
    private String corsAllowedOrigins;

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        if (enableCors) {
            registry.addMapping("/**")
                    .allowedOrigins(CorsOriginResolver.resolve(frontendUrl, corsAllowedOrigins))
                    .allowedMethods("HEAD", "OPTIONS", "GET", "POST", "PUT", "PATCH", "DELETE")
                    .allowedHeaders("*")
                    .maxAge(MAX_AGE_SECS);
        } else registry.addMapping("/**").allowedMethods("*");
    }

    @Override
    public void addArgumentResolvers(List<HandlerMethodArgumentResolver> argumentResolvers) {
        argumentResolvers.add(currentUserResolver);
    }

    @Override
    public void addResourceHandlers(ResourceHandlerRegistry registry) {
        registry.addResourceHandler("/images/**")
                .addResourceLocations("classpath:/static/images/")
                .addResourceLocations("file:/app/static/images/");
    }
}
