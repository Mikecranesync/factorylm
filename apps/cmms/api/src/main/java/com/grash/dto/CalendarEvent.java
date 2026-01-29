package com.grash.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Date;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class CalendarEvent<T> {
    private String type;
    private T event;
    private Date date;
}
