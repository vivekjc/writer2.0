import React, { useState } from 'react';
import { Container, Paper, Stepper, Step, StepLabel, Typography, Button } from '@mui/material';
import OutlineGenerator from './components/OutlineGenerator';
import ChapterBreakdown from './components/ChapterBreakdown';
import ResponseBreakdown from './components/ResponseBreakdown';
import BookGenerator from './components/BookGenerator';

const steps = ['Generate Outline', 'Break Down Chapters', 'Plan Responses', 'Generate Book'];

function App() {
  const [activeStep, setActiveStep] = useState(0);
  const [outline, setOutline] = useState<string>('');
  const [chapterBreakdown, setChapterBreakdown] = useState<any[]>([]);
  const [responseBreakdown, setResponseBreakdown] = useState<any[]>([]);

  const handleNext = () => {
    setActiveStep((prevStep) => prevStep + 1);
  };

  const handleBack = () => {
    setActiveStep((prevStep) => prevStep - 1);
  };

  const getStepContent = (step: number) => {
    switch (step) {
      case 0:
        return <OutlineGenerator onOutlineGenerated={(outline: string) => {
          setOutline(outline);
          handleNext();
        }} />;
      case 1:
        return <ChapterBreakdown 
          outline={outline}
          onBreakdownComplete={(breakdown: any[]) => {
            setChapterBreakdown(breakdown);
            handleNext();
          }}
        />;
      case 2:
        return <ResponseBreakdown
          chapters={chapterBreakdown}
          onBreakdownComplete={(breakdown: any[]) => {
            setResponseBreakdown(breakdown);
            handleNext();
          }}
        />;
      case 3:
        return <BookGenerator 
          chapterBreakdown={responseBreakdown}
        />;
      default:
        return 'Unknown step';
    }
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Paper sx={{ p: 4 }}>
        <Typography component="h1" variant="h4" align="center" gutterBottom>
          Software Engineer's Handbook Generator
        </Typography>
        
        <Stepper activeStep={activeStep} sx={{ pt: 3, pb: 5 }}>
          {steps.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>

        {getStepContent(activeStep)}

        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '20px' }}>
          {activeStep !== 0 && (
            <Button onClick={handleBack}>
              Back
            </Button>
          )}
          {activeStep !== steps.length - 1 && (
            <Button
              variant="contained"
              color="primary"
              onClick={handleNext}
              style={{ marginLeft: 'auto' }}
            >
              Next
            </Button>
          )}
        </div>
      </Paper>
    </Container>
  );
}

export default App; 