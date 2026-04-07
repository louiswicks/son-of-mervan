import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getProfile, updateProfile, changePassword, deleteAccount } from '../api/users';
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
