import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getProfile, updateProfile, changePassword, deleteAccount, getNotificationPreferences, updateNotificationPreferences } from '../api/users';
import { getSessions, revokeSession, revokeAllOtherSessions } from '../api/sessions';
import toast from 'react-hot-toast';

export function useProfile(options = {}) {
  return useQuery({
    queryKey: ['profile'],
    queryFn: getProfile,
    staleTime: 5 * 60 * 1000,
    ...options,
  });
}

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload) => updateProfile(payload),
    onSuccess: (data) => {
      queryClient.setQueryData(['profile'], data);
      toast.success('Profile updated.');
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || err.message || 'Update failed.';
      toast.error(msg);
    },
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: ({ currentPw, newPw }) => changePassword(currentPw, newPw),
    onSuccess: () => {
      toast.success('Password changed successfully.');
    },
    onError: (err) => {
      const detail = err.response?.data?.detail;
      const msg = Array.isArray(detail)
        ? detail.map((d) => d.msg).join(' ')
        : detail || err.message || 'Update failed.';
      toast.error(msg);
    },
  });
}

export function useDeleteAccount() {
  return useMutation({
    mutationFn: deleteAccount,
    onError: (err) => {
      toast.error(err.response?.data?.detail || err.message || 'Deletion failed.');
    },
  });
}

export function useNotificationPreferences(options = {}) {
  return useQuery({
    queryKey: ['notificationPrefs'],
    queryFn: getNotificationPreferences,
    staleTime: 5 * 60 * 1000,
    ...options,
  });
}

export function useUpdateNotificationPreferences() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload) => updateNotificationPreferences(payload),
    onSuccess: (data) => {
      queryClient.setQueryData(['notificationPrefs'], data);
      toast.success('Email preferences saved.');
    },
    onError: (err) => {
      toast.error(err.response?.data?.detail || err.message || 'Update failed.');
    },
  });
}

export function useSessions() {
  return useQuery({
    queryKey: ['sessions'],
    queryFn: getSessions,
    staleTime: 30 * 1000,
  });
}

export function useRevokeSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id) => revokeSession(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sessions'] });
      toast.success('Session signed out.');
    },
    onError: (err) => {
      toast.error(err.response?.data?.detail || err.message || 'Failed to revoke session.');
    },
  });
}

export function useRevokeAllOtherSessions() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: revokeAllOtherSessions,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['sessions'] });
      toast.success(data?.message || 'All other sessions signed out.');
    },
    onError: (err) => {
      toast.error(err.response?.data?.detail || err.message || 'Failed to revoke sessions.');
    },
  });
}
