import { Grid } from '@mui/material';
import * as React from 'react';
import RegisterJWT from '../../../pages/Auth/Register/RegisterJWT';
import { number } from 'yup';
import { getUsers } from '../../../../slices/user';
import { useDispatch } from '../../../../store';

export default function CreateUser({
  roleId,
  onClose,
  onRefreshUsers
}: {
  roleId: number;
  onClose: () => void;
  onRefreshUsers: () => void;
}) {
  const dispatch = useDispatch();
  return (
    <Grid container sx={{ pb: 3 }}>
      <RegisterJWT
        role={roleId}
        invitationMode
        onInvitationSuccess={() => {
          onClose();
          onRefreshUsers();
        }}
      />
    </Grid>
  );
}
