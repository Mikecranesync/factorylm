import { Dialog, DialogContent, DialogTitle, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';
import Form from '../../components/form';
import * as Yup from 'yup';
import { IField } from '../../type';
import { formatSelect } from '../../../../utils/formatters';
import { useDispatch } from '../../../../store';
import { createLabor } from '../../../../slices/labor';
import useAuth from '../../../../hooks/useAuth';
import FeatureErrorMessage from '../../components/FeatureErrorMessage';
import { PlanFeature } from '../../../../models/owns/subscriptionPlan';
import { getImageAndFiles } from '../../../../utils/overall';
import { createWorkOrderMeterTrigger } from '../../../../slices/workOrderMeterTrigger';
import { useContext } from 'react';
import { CompanySettingsContext } from '../../../../contexts/CompanySettingsContext';
import { addFilesToWorkOrder } from '../../../../slices/workOrder';

interface AddFileProps {
  open: boolean;
  onClose: () => void;
  workOrderId: number;
}

export default function AddFileModal({
                                       open,
                                       onClose,
                                       workOrderId
                                     }: AddFileProps) {
  const { t }: { t: any } = useTranslation();
  const dispatch = useDispatch();
  const { hasFeature } = useAuth();
  const { uploadFiles } = useContext(
    CompanySettingsContext
  );
  const fields: Array<IField> = [
    {
      name: 'files',
      type: 'file',
      multiple: true,
      label: t('files'),
      fileType: 'file'
    }
  ];
  const shape = {
    files: Yup.array().required(t('required_field'))
  };
  return (
    <Dialog fullWidth maxWidth="sm" open={open} onClose={onClose}>
      <DialogTitle
        sx={{
          p: 3
        }}
      >
        <Typography variant="h4" gutterBottom>
          {t('add_file')}
        </Typography>
      </DialogTitle>
      <DialogContent
        dividers
        sx={{
          p: 3
        }}
      >
        {hasFeature(PlanFeature.FILE) ? (
          <Form
            fields={fields}
            validation={Yup.object().shape(shape)}
            submitText={t('add')}
            values={{}}
            onSubmit={async (values) => {
              const formattedValues = { ...values };
              return new Promise<void>((resolve, rej) => {
                uploadFiles(formattedValues.files, [])
                  .then((files) => {
                    dispatch(
                      addFilesToWorkOrder(workOrderId, files)
                    ).then(onClose).then(resolve).catch(rej);
                  }).catch(rej);
              });
            }}
          />
        ) : (
          <FeatureErrorMessage message="Upgrade to add files to your Work Orders. " />
        )}
      </DialogContent>
    </Dialog>
  );
}
