package com.grash.repository;

import com.grash.model.TaskBase;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TaskBaseRepository extends JpaRepository<TaskBase, Long> {
}
