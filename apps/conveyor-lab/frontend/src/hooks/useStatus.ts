/**
 * Hook for VFD status and commands
 */

import { useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getStatus, sendCommand } from '../services/api';
import { useConveyorStore } from '../store';
import { hapticFeedback } from '../utils/telegram';

export function useStatus() {
  const queryClient = useQueryClient();
  const { status, setStatus, activeRun } = useConveyorStore();

  // Poll status every 2 seconds when no WebSocket
  const query = useQuery({
    queryKey: ['status'],
    queryFn: async () => {
      const data = await getStatus();
      setStatus(data);
      return data;
    },
    refetchInterval: 2000,
    staleTime: 1000,
  });

  const commandMutation = useMutation({
    mutationFn: async (params: {
      action: 'start' | 'stop' | 'set_speed' | 'set_direction' | 'clear_fault';
      value?: number | 'forward' | 'reverse';
    }) => {
      return sendCommand(params.action, params.value, activeRun?.id);
    },
    onSuccess: (data) => {
      setStatus(data.status);
      queryClient.invalidateQueries({ queryKey: ['status'] });
      hapticFeedback('success');
    },
    onError: () => {
      hapticFeedback('error');
    },
  });

  const start = useCallback(() => {
    commandMutation.mutate({ action: 'start' });
  }, [commandMutation]);

  const stop = useCallback(() => {
    commandMutation.mutate({ action: 'stop' });
  }, [commandMutation]);

  const setSpeed = useCallback((hz: number) => {
    commandMutation.mutate({ action: 'set_speed', value: hz });
  }, [commandMutation]);

  const setDirection = useCallback((direction: 'forward' | 'reverse') => {
    commandMutation.mutate({ action: 'set_direction', value: direction });
  }, [commandMutation]);

  const clearFault = useCallback(() => {
    commandMutation.mutate({ action: 'clear_fault' });
  }, [commandMutation]);

  return {
    status,
    isLoading: query.isLoading,
    isCommandPending: commandMutation.isPending,
    error: query.error,
    start,
    stop,
    setSpeed,
    setDirection,
    clearFault,
    refetch: query.refetch,
  };
}
