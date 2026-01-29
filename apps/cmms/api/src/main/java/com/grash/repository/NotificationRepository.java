package com.grash.repository;

import com.grash.model.Notification;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Collection;

public interface NotificationRepository extends JpaRepository<Notification, Long>, JpaSpecificationExecutor<Notification> {
    Collection<Notification> findByUser_Id(Long id);

    @Query("update Notification n set n.seen=true where n.user.id=:userId and n.seen=false")
    @Modifying
    void readAll(@Param("userId") Long userId);
}
