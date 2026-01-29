package com.grash.repository;

import com.grash.model.SubscriptionChangeRequest;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

import java.util.Collection;

public interface SubscriptionChangeRequestRepository extends JpaRepository<SubscriptionChangeRequest, Long>, JpaSpecificationExecutor<SubscriptionChangeRequest> {
    Collection<SubscriptionChangeRequest> findByCompany_Id(Long id);
}
