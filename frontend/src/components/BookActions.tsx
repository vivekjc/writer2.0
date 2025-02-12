import React from 'react';
import {
  Box,
  Button,
  ButtonGroup,
  Typography,
  Snackbar,
  Alert,
} from '@mui/material';
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';
import TextSnippetIcon from '@mui/icons-material/TextSnippet';

interface BookActionsProps {
  bookFilename: string | null;
}

const BookActions: React.FC<BookActionsProps> = ({ bookFilename }) => {
  const [snackbar, setSnackbar] = React.useState<{
    open: boolean;
    message: string;
    severity: 'success' | 'error';
  }>({
    open: false,
    message: '',
    severity: 'success',
  });

  const handleDownload = async (format: 'pdf' | 'text') => {
    if (!bookFilename) {
      setSnackbar({
        open: true,
        message: 'No book available to download',
        severity: 'error',
      });
      return;
    }

    try {
      const response = await fetch(
        `http://localhost:8000/api/download-book/${bookFilename}?format=${format}`,
        {
          method: 'GET',
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to download book: ${response.statusText}`);
      }

      // Get the filename from the Content-Disposition header if available
      const contentDisposition = response.headers.get('Content-Disposition');
      let filename = bookFilename;
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
        if (filenameMatch) {
          filename = filenameMatch[1];
        }
      }

      // Create a blob from the response
      const blob = await response.blob();
      
      // Create a temporary URL for the blob
      const url = window.URL.createObjectURL(blob);
      
      // Create a temporary link element
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      
      // Append the link to the body
      document.body.appendChild(link);
      
      // Trigger the download
      link.click();
      
      // Clean up
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      setSnackbar({
        open: true,
        message: `Book downloaded successfully as ${format.toUpperCase()}`,
        severity: 'success',
      });
    } catch (error) {
      console.error('Download error:', error);
      setSnackbar({
        open: true,
        message: 'Failed to download book. Please try again.',
        severity: 'error',
      });
    }
  };

  const handleCloseSnackbar = () => {
    setSnackbar({ ...snackbar, open: false });
  };

  return (
    <Box sx={{ mt: 2 }}>
      <Typography variant="h6" gutterBottom>
        Download Book
      </Typography>
      <ButtonGroup variant="contained" aria-label="download options">
        <Button
          startIcon={<PictureAsPdfIcon />}
          onClick={() => handleDownload('pdf')}
          disabled={!bookFilename}
        >
          Download PDF
        </Button>
        <Button
          startIcon={<TextSnippetIcon />}
          onClick={() => handleDownload('text')}
          disabled={!bookFilename}
        >
          Download Text
        </Button>
      </ButtonGroup>
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={handleCloseSnackbar}
      >
        <Alert
          onClose={handleCloseSnackbar}
          severity={snackbar.severity}
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default BookActions; 