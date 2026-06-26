package com.grash.service;

import com.grash.exception.CustomException;
import com.grash.model.OwnUser;
import com.grash.repository.UserRepository;
import com.grash.security.JwtTokenProvider;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

import javax.transaction.Transactional;
import java.util.Collections;

@Service
@RequiredArgsConstructor
@Transactional
public class HubSsoService {

    private final UserRepository userRepository;
    private final JwtTokenProvider jwtTokenProvider;

    @Value("${hub.sso.secret:}")
    private String hubSsoSecret;

    @Value("${hub.sso.issuer:factorylm-hub}")
    private String hubSsoIssuer;

    @Value("${hub.sso.audience:atlas-cmms}")
    private String hubSsoAudience;

    public String exchangeAssertion(String assertion) {
        if (hubSsoSecret == null || hubSsoSecret.trim().isEmpty()) {
            throw new CustomException("Hub SSO is not configured", HttpStatus.SERVICE_UNAVAILABLE);
        }

        Claims claims = parseClaims(assertion);
        String email = extractEmail(claims);
        OwnUser user = userRepository.findByEmailIgnoreCase(email)
                .orElseThrow(() -> new CustomException("Atlas user is not provisioned", HttpStatus.FORBIDDEN));

        if (!user.isEnabled()) {
            throw new CustomException("Atlas user is disabled", HttpStatus.UNAUTHORIZED);
        }

        return jwtTokenProvider.createToken(user.getEmail(), Collections.singletonList(user.getRole().getRoleType()));
    }

    private Claims parseClaims(String assertion) {
        try {
            return Jwts.parser()
                    .setSigningKey(hubSsoSecret)
                    .requireIssuer(hubSsoIssuer)
                    .requireAudience(hubSsoAudience)
                    .parseClaimsJws(assertion)
                    .getBody();
        } catch (JwtException | IllegalArgumentException e) {
            throw new CustomException("Invalid Hub SSO assertion", HttpStatus.FORBIDDEN);
        }
    }

    private String extractEmail(Claims claims) {
        String email = claims.get("email", String.class);
        if (email == null || email.trim().isEmpty()) {
            email = claims.getSubject();
        }
        if (email == null || email.trim().isEmpty()) {
            throw new CustomException("Hub SSO assertion is missing email", HttpStatus.FORBIDDEN);
        }
        return email.trim().toLowerCase();
    }
}
