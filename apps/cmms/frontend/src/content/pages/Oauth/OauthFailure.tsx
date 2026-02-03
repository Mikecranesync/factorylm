import SuspenseLoader from '../../../components/SuspenseLoader';
import { useContext, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import useAuth from '../../../hooks/useAuth';
import { CustomSnackBarContext } from '../../../contexts/CustomSnackBarContext';

export default function OauthFailure() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { loginInternal } = useAuth();
  const error = searchParams.get('error');
  const { showSnackBar } = useContext(CustomSnackBarContext);
  const navigate = useNavigate();

  useEffect(() => {
    if (error) {
      showSnackBar(error, 'error');
      navigate('/account/login');
    }
  }, [error]);
  return <SuspenseLoader />;
}
