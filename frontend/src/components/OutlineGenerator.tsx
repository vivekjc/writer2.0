import React, { useState } from 'react';
import { TextField, Button, CircularProgress, Box, Typography } from '@mui/material';
import axios from 'axios';

interface OutlineGeneratorProps {
  onOutlineGenerated: (outline: string) => void;
}

const OutlineGenerator: React.FC<OutlineGeneratorProps> = ({ onOutlineGenerated }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pageCount, setPageCount] = useState<number>(200); // Default to 200 pages

  const handleGenerateOutline = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await axios.post('http://localhost:8000/api/generate-outline', {
        prompt: `write an extensive book on Software Engineering. The idea here is to provide a handbook to every new software engineer and also to experienced engineers. The focus is not on specific technologies but provide a general approach to every software engineering problem no matter the size. The heavy focus is on tradeoff for making every decision, and around documentation one should have and around the lifecycle of a software engineering process. The book should be approximately ${pageCount} pages long, with each page containing 800-1000 words. Please provide a detailed outline with chapter titles and suggested word counts for each chapter based on the importance and depth of the topic.`,
        pageCount: pageCount
      });

      if (response.data.outline) {
        onOutlineGenerated(response.data.outline);
      } else {
        setError('Failed to generate outline');
      }
    } catch (err) {
      setError('Error generating outline. Please try again.');
      console.error('Error:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ mt: 2 }}>
      <Typography variant="h6" gutterBottom>
        Generate Book Outline
      </Typography>
      <Typography variant="body1" sx={{ mb: 2 }}>
        Specify the desired length of your book and generate a detailed outline.
      </Typography>
      
      <TextField
        label="Number of Pages"
        type="number"
        value={pageCount}
        onChange={(e) => setPageCount(Math.max(1, parseInt(e.target.value) || 0))}
        sx={{ mb: 2 }}
        helperText="Each page is approximately 800-1000 words"
        fullWidth
      />
      
      <Button
        variant="contained"
        color="primary"
        onClick={handleGenerateOutline}
        disabled={loading}
        sx={{ mt: 2 }}
      >
        {loading ? <CircularProgress size={24} /> : 'Generate Outline'}
      </Button>

      {error && (
        <Typography color="error" sx={{ mt: 2 }}>
          {error}
        </Typography>
      )}
    </Box>
  );
};

export default OutlineGenerator; 