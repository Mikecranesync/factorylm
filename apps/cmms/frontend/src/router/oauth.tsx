import { lazy, Suspense } from 'react';

import SuspenseLoader from 'src/components/SuspenseLoader';
import Guest from 'src/components/Guest';

const Loader = (Component) => (props) =>
  (
    <Suspense fallback={<SuspenseLoader />}>
      <Component {...props} />
    </Suspense>
  );

const OauthSuccess = Loader(
  lazy(() => import('../content/pages/Oauth/OauthSuccess'))
);

const OauthFailure = Loader(
  lazy(() => import('../content/pages/Oauth/OauthFailure'))
);

const oauthRoutes = [
  {
    path: 'success',
    element: (
      <Guest>
        <OauthSuccess />{' '}
      </Guest>
    )
  },
  { path: 'failure', element: <OauthFailure /> }
];

export default oauthRoutes;
