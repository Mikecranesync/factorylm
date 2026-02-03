import { Box, styled } from '@mui/material';
import { Link } from 'react-router-dom';

const LogoWrapper = styled(Link)(
  ({ theme }) => `
        color: ${theme.palette.text.primary};
        padding: ${theme.spacing(0, 1, 0, 0)};
        display: flex;
        text-decoration: none;
        font-weight: ${theme.typography.fontWeightBold};
        align-items: center;
`
);

const LogoIcon = styled(Box)(
  ({ theme }) => `
        background: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%);
        width: 32px;
        height: 32px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-right: 8px;
`
);

const LogoText = styled(Box)(
  ({ theme }) => `
        font-size: ${theme.typography.pxToRem(18)};
        font-weight: 700;
        color: ${theme.palette.text.primary};
        display: flex;
        align-items: center;
`
);

const LogoAccent = styled('span')(
  () => `
        background: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
`
);

function Logo() {
  return (
    <LogoWrapper to="/app/work-orders">
      <LogoIcon>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
          <path d="M4 20V10L10 13V7L16 10V20H4Z" fill="white"/>
          <rect x="7" y="14" width="3" height="4" fill="#6366f1"/>
          <rect x="12" y="13" width="2" height="5" fill="#6366f1"/>
        </svg>
      </LogoIcon>
      <Box
        component="span"
        sx={{
          display: { xs: 'none', sm: 'inline-block' }
        }}
      >
        <LogoText>
          Factory<LogoAccent>LM</LogoAccent>
        </LogoText>
      </Box>
    </LogoWrapper>
  );
}

export default Logo;
