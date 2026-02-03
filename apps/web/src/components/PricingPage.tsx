import React, { useState } from 'react';
import {
  Box,
  Container,
  Typography,
  Card,
  CardContent,
  Button,
  Chip,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  TextField,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  useTheme,
  alpha,
} from '@mui/material';
import {
  Check as CheckIcon,
  ExpandMore as ExpandMoreIcon,
  Calculate as CalculateIcon,
  ContactSupport as ContactIcon,
  Security as SecurityIcon,
  Speed as SpeedIcon,
  Groups as GroupsIcon,
  CloudDone as CloudIcon,
} from '@mui/icons-material';

interface PricingTier {
  name: string;
  price: string;
  popular?: boolean;
  features: string[];
  buttonText: string;
  buttonVariant: 'outlined' | 'contained';
}

interface Feature {
  name: string;
  starter: boolean | string;
  professional: boolean | string;
  enterprise: boolean | string;
}

const pricingTiers: PricingTier[] = [
  {
    name: 'Starter',
    price: '$99',
    features: [
      'Up to 5 technicians',
      '1 PLC connection',
      'Basic alarm triage',
      'Email support',
      'Manual lookup (100/month)',
    ],
    buttonText: 'Start Free Trial',
    buttonVariant: 'outlined',
  },
  {
    name: 'Professional',
    price: '$499',
    popular: true,
    features: [
      'Up to 25 technicians',
      '10 PLC connections',
      'Advanced alarm triage + AI recommendations',
      'Priority support',
      'Unlimited manual lookup',
      'Custom integrations',
    ],
    buttonText: 'Start Free Trial',
    buttonVariant: 'contained',
  },
  {
    name: 'Enterprise',
    price: 'Contact Sales',
    features: [
      'Unlimited technicians',
      'Unlimited PLCs',
      'Dedicated success manager',
      'On-premise option',
      'SLA guarantees',
      'Custom training',
    ],
    buttonText: 'Contact Sales',
    buttonVariant: 'outlined',
  },
];

const featureComparison: Feature[] = [
  { name: 'Number of technicians', starter: 'Up to 5', professional: 'Up to 25', enterprise: 'Unlimited' },
  { name: 'PLC connections', starter: '1', professional: '10', enterprise: 'Unlimited' },
  { name: 'Basic alarm triage', starter: true, professional: true, enterprise: true },
  { name: 'AI-powered recommendations', starter: false, professional: true, enterprise: true },
  { name: 'Manual lookup', starter: '100/month', professional: 'Unlimited', enterprise: 'Unlimited' },
  { name: 'Email support', starter: true, professional: true, enterprise: true },
  { name: 'Priority support', starter: false, professional: true, enterprise: true },
  { name: 'Custom integrations', starter: false, professional: true, enterprise: true },
  { name: 'Dedicated success manager', starter: false, professional: false, enterprise: true },
  { name: 'On-premise deployment', starter: false, professional: false, enterprise: true },
  { name: 'SLA guarantees', starter: false, professional: false, enterprise: true },
  { name: 'Custom training', starter: false, professional: false, enterprise: true },
];

const faqItems = [
  {
    question: 'What is included in the free trial?',
    answer: 'Our 14-day free trial includes full access to all features of your chosen plan. No credit card required.',
  },
  {
    question: 'Can I change plans later?',
    answer: 'Yes, you can upgrade or downgrade your plan at any time. Changes will be reflected in your next billing cycle.',
  },
  {
    question: 'What happens if I exceed my plan limits?',
    answer: 'We\'ll notify you when you approach your limits. You can either upgrade your plan or purchase additional capacity.',
  },
  {
    question: 'Do you offer volume discounts?',
    answer: 'Yes, we offer custom pricing for large organizations. Contact our sales team for a personalized quote.',
  },
  {
    question: 'Is my data secure?',
    answer: 'Absolutely. We use enterprise-grade security measures including encryption, regular security audits, and compliance with industry standards.',
  },
  {
    question: 'Do you support on-premise deployments?',
    answer: 'Yes, on-premise deployment is available with our Enterprise plan. Contact us for more details.',
  },
];

const ROICalculator: React.FC = () => {
  const [technicians, setTechnicians] = useState<number>(10);
  const [downtimeCost, setDowntimeCost] = useState<number>(5000);
  const theme = useTheme();

  const calculateSavings = () => {
    // Assumptions: 20% reduction in downtime, 1 incident per month
    const monthlySavings = downtimeCost * 0.2;
    const annualSavings = monthlySavings * 12;
    const planCost = technicians <= 5 ? 99 * 12 : technicians <= 25 ? 499 * 12 : 0;
    const netSavings = annualSavings - planCost;
    const roi = planCost > 0 ? ((netSavings / planCost) * 100).toFixed(0) : 0;

    return {
      monthlySavings: monthlySavings.toLocaleString(),
      annualSavings: annualSavings.toLocaleString(),
      netSavings: netSavings.toLocaleString(),
      roi,
    };
  };

  const savings = calculateSavings();

  return (
    <Card sx={{ mt: 4, background: alpha(theme.palette.primary.main, 0.02) }}>
      <CardContent sx={{ p: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
          <CalculateIcon sx={{ mr: 1, color: 'primary.main' }} />
          <Typography variant="h4" component="h2">
            ROI Calculator
          </Typography>
        </Box>
        
        <Grid container spacing={4}>
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Number of Technicians"
              type="number"
              value={technicians}
              onChange={(e) => setTechnicians(Number(e.target.value))}
              sx={{ mb: 3 }}
            />
            <TextField
              fullWidth
              label="Average Cost per Downtime Incident"
              type="number"
              value={downtimeCost}
              onChange={(e) => setDowntimeCost(Number(e.target.value))}
              InputProps={{ startAdornment: '$' }}
            />
          </Grid>
          
          <Grid item xs={12} md={6}>
            <Box sx={{ p: 3, border: '2px solid', borderColor: 'primary.main', borderRadius: 2 }}>
              <Typography variant="h6" sx={{ mb: 2, color: 'primary.main' }}>
                Estimated Savings
              </Typography>
              <Typography variant="body1" sx={{ mb: 1 }}>
                Monthly Savings: <strong>${savings.monthlySavings}</strong>
              </Typography>
              <Typography variant="body1" sx={{ mb: 1 }}>
                Annual Savings: <strong>${savings.annualSavings}</strong>
              </Typography>
              <Typography variant="body1" sx={{ mb: 1 }}>
                Net Annual Savings: <strong>${savings.netSavings}</strong>
              </Typography>
              <Typography variant="h6" sx={{ color: 'success.main' }}>
                ROI: {savings.roi}%
              </Typography>
            </Box>
          </Grid>
        </Grid>
        
        <Typography variant="body2" sx={{ mt: 2, color: 'text.secondary', fontStyle: 'italic' }}>
          *Based on industry average of 20% reduction in downtime incidents
        </Typography>
      </CardContent>
    </Card>
  );
};

const PricingPage: React.FC = () => {
  const theme = useTheme();

  return (
    <Box sx={{ bgcolor: 'background.default', minHeight: '100vh', py: 8 }}>
      <Container maxWidth="lg">
        {/* Hero Section */}
        <Box sx={{ textAlign: 'center', mb: 8 }}>
          <Typography variant="h2" component="h1" sx={{ mb: 2, fontWeight: 'bold' }}>
            Choose Your FactoryLM Plan
          </Typography>
          <Typography variant="h5" sx={{ color: 'text.secondary', mb: 4 }}>
            Streamline your maintenance operations with AI-powered insights
          </Typography>
          
          {/* Value Props Icons */}
          <Grid container spacing={4} sx={{ mt: 4, mb: 6 }}>
            <Grid item xs={12} sm={3}>
              <Box sx={{ textAlign: 'center' }}>
                <SpeedIcon sx={{ fontSize: 48, color: 'primary.main', mb: 1 }} />
                <Typography variant="h6">Faster Resolution</Typography>
                <Typography variant="body2" color="text.secondary">
                  Reduce downtime by 20%
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Box sx={{ textAlign: 'center' }}>
                <SecurityIcon sx={{ fontSize: 48, color: 'primary.main', mb: 1 }} />
                <Typography variant="h6">Enterprise Security</Typography>
                <Typography variant="body2" color="text.secondary">
                  SOC2 compliant platform
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Box sx={{ textAlign: 'center' }}>
                <GroupsIcon sx={{ fontSize: 48, color: 'primary.main', mb: 1 }} />
                <Typography variant="h6">Team Collaboration</Typography>
                <Typography variant="body2" color="text.secondary">
                  Connect all technicians
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Box sx={{ textAlign: 'center' }}>
                <CloudIcon sx={{ fontSize: 48, color: 'primary.main', mb: 1 }} />
                <Typography variant="h6">Cloud or On-Premise</Typography>
                <Typography variant="body2" color="text.secondary">
                  Deploy your way
                </Typography>
              </Box>
            </Grid>
          </Grid>
        </Box>

        {/* Pricing Cards */}
        <Grid container spacing={4} sx={{ mb: 8 }}>
          {pricingTiers.map((tier, index) => (
            <Grid item xs={12} md={4} key={tier.name}>
              <Card
                sx={{
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  position: 'relative',
                  border: tier.popular ? `2px solid ${theme.palette.primary.main}` : '1px solid',
                  borderColor: tier.popular ? 'primary.main' : 'divider',
                  '&:hover': {
                    transform: 'translateY(-4px)',
                    transition: 'transform 0.3s ease-in-out',
                    boxShadow: theme.shadows[8],
                  },
                }}
              >
                {tier.popular && (
                  <Chip
                    label="Most Popular"
                    color="primary"
                    sx={{
                      position: 'absolute',
                      top: -12,
                      left: '50%',
                      transform: 'translateX(-50%)',
                      fontWeight: 'bold',
                    }}
                  />
                )}
                
                <CardContent sx={{ flexGrow: 1, p: 4 }}>
                  <Typography variant="h4" component="h2" sx={{ mb: 1, fontWeight: 'bold' }}>
                    {tier.name}
                  </Typography>
                  
                  <Box sx={{ mb: 3 }}>
                    <Typography variant="h3" component="span" sx={{ fontWeight: 'bold' }}>
                      {tier.price}
                    </Typography>
                    {tier.price !== 'Contact Sales' && (
                      <Typography variant="body1" component="span" sx={{ color: 'text.secondary' }}>
                        /month
                      </Typography>
                    )}
                  </Box>

                  <Box sx={{ mb: 4 }}>
                    {tier.features.map((feature, featureIndex) => (
                      <Box key={featureIndex} sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                        <CheckIcon sx={{ color: 'success.main', mr: 1, fontSize: 20 }} />
                        <Typography variant="body2">{feature}</Typography>
                      </Box>
                    ))}
                  </Box>

                  <Button
                    variant={tier.buttonVariant}
                    color="primary"
                    size="large"
                    fullWidth
                    sx={{ mt: 'auto', py: 1.5 }}
                  >
                    {tier.buttonText}
                  </Button>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>

        {/* ROI Calculator */}
        <ROICalculator />

        {/* Feature Comparison Table */}
        <Box sx={{ mt: 8, mb: 8 }}>
          <Typography variant="h4" component="h2" sx={{ mb: 4, textAlign: 'center' }}>
            Feature Comparison
          </Typography>
          
          <TableContainer component={Paper} sx={{ boxShadow: theme.shadows[4] }}>
            <Table>
              <TableHead>
                <TableRow sx={{ bgcolor: 'primary.main' }}>
                  <TableCell sx={{ color: 'primary.contrastText', fontWeight: 'bold' }}>
                    Features
                  </TableCell>
                  <TableCell align="center" sx={{ color: 'primary.contrastText', fontWeight: 'bold' }}>
                    Starter
                  </TableCell>
                  <TableCell align="center" sx={{ color: 'primary.contrastText', fontWeight: 'bold' }}>
                    Professional
                  </TableCell>
                  <TableCell align="center" sx={{ color: 'primary.contrastText', fontWeight: 'bold' }}>
                    Enterprise
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {featureComparison.map((feature, index) => (
                  <TableRow key={feature.name} sx={{ '&:nth-of-type(odd)': { bgcolor: 'action.hover' } }}>
                    <TableCell component="th" scope="row" sx={{ fontWeight: 500 }}>
                      {feature.name}
                    </TableCell>
                    <TableCell align="center">
                      {typeof feature.starter === 'boolean' ? (
                        feature.starter ? (
                          <CheckIcon sx={{ color: 'success.main' }} />
                        ) : (
                          '—'
                        )
                      ) : (
                        feature.starter
                      )}
                    </TableCell>
                    <TableCell align="center">
                      {typeof feature.professional === 'boolean' ? (
                        feature.professional ? (
                          <CheckIcon sx={{ color: 'success.main' }} />
                        ) : (
                          '—'
                        )
                      ) : (
                        feature.professional
                      )}
                    </TableCell>
                    <TableCell align="center">
                      {typeof feature.enterprise === 'boolean' ? (
                        feature.enterprise ? (
                          <CheckIcon sx={{ color: 'success.main' }} />
                        ) : (
                          '—'
                        )
                      ) : (
                        feature.enterprise
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>

        {/* FAQ Section */}
        <Box sx={{ mt: 8 }}>
          <Typography variant="h4" component="h2" sx={{ mb: 4, textAlign: 'center' }}>
            Frequently Asked Questions
          </Typography>
          
          {faqItems.map((faq, index) => (
            <Accordion key={index} sx={{ mb: 2 }}>
              <AccordionSummary
                expandIcon={<ExpandMoreIcon />}
                sx={{ '&:hover': { bgcolor: 'action.hover' } }}
              >
                <Typography variant="h6">{faq.question}</Typography>
              </AccordionSummary>
              <AccordionDetails>
                <Typography>{faq.answer}</Typography>
              </AccordionDetails>
            </Accordion>
          ))}
        </Box>

        {/* Final CTA */}
        <Box sx={{ textAlign: 'center', mt: 8, p: 6, bgcolor: alpha(theme.palette.primary.main, 0.05), borderRadius: 2 }}>
          <Typography variant="h4" sx={{ mb: 2 }}>
            Ready to Transform Your Maintenance Operations?
          </Typography>
          <Typography variant="body1" sx={{ mb: 4, color: 'text.secondary' }}>
            Join hundreds of manufacturers already using FactoryLM to reduce downtime and improve efficiency.
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center', flexWrap: 'wrap' }}>
            <Button variant="contained" color="primary" size="large" startIcon={<SpeedIcon />}>
              Start Free Trial
            </Button>
            <Button variant="outlined" color="primary" size="large" startIcon={<ContactIcon />}>
              Schedule Demo
            </Button>
          </Box>
        </Box>
      </Container>
    </Box>
  );
};

export default PricingPage;